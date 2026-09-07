"""FastAPI application exposing health and structured extraction endpoints."""

from http import HTTPStatus
from typing import cast

from fastapi import Depends, FastAPI, File, Form, Path as PathParameter, Request, UploadFile
from fastapi.exceptions import RequestValidationError as FastAPIRequestValidationError
from fastapi.responses import JSONResponse

from src.model_service import ModelService
from src.model_store import ModelStore
from src.models import (
    ArtifactTooLargeError,
    DuplicateVersionError,
    InvalidRegistrationError,
    ModelVersion,
    ModelVersionNotFoundError,
)
from src.schemas import (
    ErrorResponse,
    ExtractionError,
    ModelVersionHistoryResponse,
    ModelVersionResponse,
    RequestValidationError,
    SchemaValidationError,
    parse_extraction_request,
    parse_metadata,
)
from src.service import OpenAIStructuredExtractor, StructuredExtractor, extract_texts
from src.settings import Settings


def _extractor(request: Request) -> StructuredExtractor:
    """Return the configured extractor or initialize the production adapter."""
    current = cast(StructuredExtractor | None, request.app.state.extractor)
    if current is None:
        try:
            current = OpenAIStructuredExtractor()
        except Exception:
            raise ExtractionError("Extraction service failed") from None
        request.app.state.extractor = current
    return current


async def _model_service(request: Request) -> ModelService:
    """Return the model service configured for the application."""
    return cast(ModelService, request.app.state.model_service)


def create_app(
    extractor: StructuredExtractor | None = None,
    settings: Settings | None = None,
    model_service: ModelService | None = None,
) -> FastAPI:
    """Create the configured HTTP application."""
    application_settings = settings or Settings.from_environment()
    registry_service = model_service or ModelService(
        ModelStore(
            application_settings.database_path,
            application_settings.data_dir,
            application_settings.max_artifact_size,
        )
    )
    application = FastAPI(title="AI Model Registry API", version="1.0.0")
    application.state.extractor = extractor
    application.state.settings = application_settings
    application.state.model_service = registry_service

    def error_response(
        error: Exception, status_code: HTTPStatus, limit: int | None = None
    ) -> JSONResponse:
        """Convert a domain error into the shared HTTP error shape."""
        content = ErrorResponse(detail=str(error), limit=limit).model_dump(
            exclude_none=True
        )
        return JSONResponse(content, status_code=status_code)

    @application.exception_handler(ModelVersionNotFoundError)
    async def handle_not_found(
        request: Request, error: ModelVersionNotFoundError
    ) -> JSONResponse:
        """Map absent registry records to HTTP 404."""
        return error_response(error, HTTPStatus.NOT_FOUND)

    @application.exception_handler(DuplicateVersionError)
    async def handle_duplicate(
        request: Request, error: DuplicateVersionError
    ) -> JSONResponse:
        """Map immutable version conflicts to HTTP 409."""
        return error_response(error, HTTPStatus.CONFLICT)

    @application.exception_handler(ArtifactTooLargeError)
    async def handle_too_large(
        request: Request, error: ArtifactTooLargeError
    ) -> JSONResponse:
        """Map artifact limit failures to HTTP 413."""
        return error_response(
            error, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, limit=error.limit
        )

    @application.exception_handler(InvalidRegistrationError)
    async def handle_invalid_registration(
        request: Request, error: InvalidRegistrationError
    ) -> JSONResponse:
        """Map invalid model registration values to HTTP 422."""
        return error_response(error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @application.exception_handler(FastAPIRequestValidationError)
    async def handle_request_validation(
        request: Request, error: FastAPIRequestValidationError
    ) -> JSONResponse:
        """Map framework validation failures to the shared error shape."""
        detail = error.errors()[0].get("msg", "Invalid request") if error.errors() else "Invalid request"
        return error_response(ValueError(str(detail)), HTTPStatus.UNPROCESSABLE_ENTITY)

    def model_response(version: ModelVersion) -> ModelVersionResponse:
        """Convert a domain version into its HTTP schema."""
        return ModelVersionResponse.model_validate(version)

    @application.get("/ping")
    async def ping() -> dict[str, str]:
        """Return the service availability payload."""
        return {"message": "pong"}

    @application.post("/entities")
    async def extract_entities(request: Request) -> JSONResponse:
        """Extract ordered structured objects from submitted texts."""
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                {"detail": "Invalid JSON body"}, status_code=HTTPStatus.BAD_REQUEST
            )
        try:
            extraction = parse_extraction_request(payload)
        except (RequestValidationError, SchemaValidationError) as error:
            return JSONResponse(
                {"detail": str(error)}, status_code=HTTPStatus.UNPROCESSABLE_ENTITY
            )
        try:
            response = extract_texts(
                extraction.texts, extraction.schema, _extractor(request)
            )
        except ExtractionError:
            return JSONResponse(
                {"detail": "Extraction service failed"},
                status_code=HTTPStatus.BAD_GATEWAY,
            )
        return JSONResponse(response.to_dict())

    @application.post(
        "/models/{model_name}/versions",
        response_model=ModelVersionResponse,
        status_code=HTTPStatus.CREATED,
        responses={
            HTTPStatus.CONFLICT: {"model": ErrorResponse},
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
            HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        },
    )
    async def register_model_version(
        model_name: str = PathParameter(min_length=1),
        artifact: UploadFile = File(),
        version: int | None = Form(None),
        description: str | None = Form(None),
        metadata: str | None = Form(None),
        service: ModelService = Depends(_model_service),
    ) -> ModelVersionResponse:
        """Register one immutable opaque model artifact."""
        try:
            parsed_metadata = parse_metadata(metadata)
        except ValueError as error:
            raise InvalidRegistrationError(str(error)) from error
        registered = service.register(
            model_name, artifact.file, version, description, parsed_metadata
        )
        return model_response(registered)

    @application.get(
        "/models/{model_name}/versions",
        response_model=ModelVersionHistoryResponse,
        responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
    )
    async def list_model_versions(
        model_name: str = PathParameter(min_length=1),
        service: ModelService = Depends(_model_service),
    ) -> ModelVersionHistoryResponse:
        """Return complete version history in descending order."""
        versions = service.history(model_name)
        return ModelVersionHistoryResponse(
            model_name=versions[0].model_name,
            versions=[model_response(version) for version in versions],
        )

    @application.get(
        "/models/{model_name}/versions/{version}",
        response_model=ModelVersionResponse,
        responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
    )
    async def get_model_version(
        model_name: str = PathParameter(min_length=1),
        version: int = PathParameter(ge=1),
        service: ModelService = Depends(_model_service),
    ) -> ModelVersionResponse:
        """Return one registered model version."""
        return model_response(service.get(model_name, version))

    @application.post(
        "/models/{model_name}/versions/{version}/activate",
        response_model=ModelVersionResponse,
        responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
    )
    async def activate_model_version(
        model_name: str = PathParameter(min_length=1),
        version: int = PathParameter(ge=1),
        service: ModelService = Depends(_model_service),
    ) -> ModelVersionResponse:
        """Make one registered version active for its model."""
        return model_response(service.activate(model_name, version))

    return application


app = create_app()
