"""FastAPI application for extraction and versioned model management."""

from http import HTTPStatus
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Path as PathParameter, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.model_service import ModelService
from src.model_store import ModelStore
from src.models import (
    ArtifactTooLargeError,
    DuplicateVersionError,
    IneligibleVersionError,
    InvalidRegistrationError,
    ModelVersion,
    ModelVersionNotFoundError,
)
from src.schemas import ErrorResponse, ModelVersionHistoryResponse, ModelVersionResponse, parse_metadata
from src.service import get_mocked_entities
from src.settings import Settings


async def get_model_service(request: Request) -> ModelService:
    """Return the model service configured for the current application."""
    return request.app.state.model_service


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create a configured HTTP application."""
    application_settings = settings or Settings.from_environment()
    store = ModelStore(
        application_settings.database_path,
        application_settings.data_dir,
        application_settings.max_artifact_size,
    )
    service = ModelService(store)
    application = FastAPI(title="Versioned Model Store API", version="1.0.0")
    application.state.settings = application_settings
    application.state.model_store = store
    application.state.model_service = service

    @application.exception_handler(ModelVersionNotFoundError)
    async def handle_not_found(request: object, error: ModelVersionNotFoundError) -> JSONResponse:
        """Map absent catalog records to HTTP 404."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(), status_code=HTTPStatus.NOT_FOUND
        )

    @application.exception_handler(DuplicateVersionError)
    async def handle_duplicate(request: object, error: DuplicateVersionError) -> JSONResponse:
        """Map immutable identity conflicts to HTTP 409."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(), status_code=HTTPStatus.CONFLICT
        )

    @application.exception_handler(IneligibleVersionError)
    async def handle_ineligible(request: object, error: IneligibleVersionError) -> JSONResponse:
        """Map lifecycle eligibility failures to HTTP 409."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(), status_code=HTTPStatus.CONFLICT
        )

    @application.exception_handler(ArtifactTooLargeError)
    async def handle_too_large(request: object, error: ArtifactTooLargeError) -> JSONResponse:
        """Map artifact limit failures to HTTP 413."""
        return JSONResponse(
            ErrorResponse(detail=str(error), limit=error.limit).model_dump(),
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )

    @application.exception_handler(InvalidRegistrationError)
    async def handle_invalid(request: object, error: InvalidRegistrationError) -> JSONResponse:
        """Map invalid registration content to HTTP 422."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(),
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation(request: object, error: RequestValidationError) -> JSONResponse:
        """Map framework request validation to the standard error shape."""
        detail = error.errors()[0].get("msg", "Invalid request") if error.errors() else "Invalid request"
        return JSONResponse(
            ErrorResponse(detail=str(detail)).model_dump(),
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    @application.get("/ping")
    async def ping() -> dict[str, str]:
        """Return the service availability payload."""
        return {"message": "pong"}

    @application.post("/entities")
    async def extract_entities(payload: dict[str, str]) -> dict[str, object]:
        """Return the existing mocked extraction response."""
        return {"entities": get_mocked_entities(payload.get("text", ""))}

    def response(version_record: ModelVersion) -> ModelVersionResponse:
        """Convert a domain version to its HTTP response schema."""
        return ModelVersionResponse.model_validate(version_record)

    @application.post(
        "/models/{model_name}/versions",
        response_model=ModelVersionResponse,
        status_code=HTTPStatus.CREATED,
        responses={
            409: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    async def register_model_version(
        model_name: str = PathParameter(min_length=1),
        artifact: UploadFile = File(...),
        version: Optional[int] = Form(None),
        description: Optional[str] = Form(None),
        metadata: Optional[str] = Form(None),
        model_service: ModelService = Depends(get_model_service),
    ) -> ModelVersionResponse:
        """Register one immutable opaque model artifact."""
        try:
            parsed_metadata = parse_metadata(metadata)
        except ValueError as exc:
            raise InvalidRegistrationError(str(exc)) from exc
        return response(
            model_service.register(model_name, artifact.file, version, description, parsed_metadata)
        )

    @application.get(
        "/models/{model_name}/versions",
        response_model=ModelVersionHistoryResponse,
        responses={404: {"model": ErrorResponse}},
    )
    async def list_model_versions(
        model_name: str = PathParameter(min_length=1),
        model_service: ModelService = Depends(get_model_service),
    ) -> ModelVersionHistoryResponse:
        """List complete model history in descending version order."""
        versions = model_service.history(model_name)
        return ModelVersionHistoryResponse(
            model_name=versions[0].model_name,
            versions=[response(item) for item in versions],
        )

    @application.get(
        "/models/{model_name}/versions/{version}",
        response_model=ModelVersionResponse,
        responses={404: {"model": ErrorResponse}},
    )
    async def get_model_version(
        model_name: str = PathParameter(min_length=1),
        version: int = PathParameter(ge=1),
        model_service: ModelService = Depends(get_model_service),
    ) -> ModelVersionResponse:
        """Retrieve one registered model version."""
        return response(model_service.get(model_name, version))

    @application.post(
        "/models/{model_name}/versions/{version}/activate",
        response_model=ModelVersionResponse,
        responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    )
    async def activate_model_version(
        model_name: str = PathParameter(min_length=1),
        version: int = PathParameter(ge=1),
        model_service: ModelService = Depends(get_model_service),
    ) -> ModelVersionResponse:
        """Atomically activate one eligible model version."""
        return response(model_service.activate(model_name, version))

    return application


app = create_app()
