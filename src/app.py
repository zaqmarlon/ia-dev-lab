"""FastAPI application for extraction and versioned model management."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from http import HTTPStatus
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Path as PathParameter, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.extraction import (
    ExtractionRequestError,
    ExtractionVolumeError,
    ModelCatalog,
    StubModelCatalog,
)
from src.inference import InferenceProvider, StubInferenceProvider
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
from src.schemas import (
    ErrorResponse,
    ExtractionRequest,
    ExtractionResponse,
    ExtractionTaskRequest,
    ModelVersionHistoryResponse,
    ModelVersionResponse,
    ResultsPendingResponse,
    RunningTaskCounts,
    RunningTaskProgress,
    RunningTaskSummaryResponse,
    TaskProgress,
    TaskResultsResponse,
    TaskStatusResponse,
    parse_metadata,
)
from src.service import ExtractionService, get_mocked_entities
from src.settings import Settings
from src.task_repository import TaskRepository
from src.task_service import (
    AuthenticatedPrincipal,
    BearerAuthenticator,
    ExtractionTaskService,
    RejectingBearerAuthenticator,
    ResultsPendingError,
    TaskExpiredError,
    TaskNotFoundError,
    UnauthorizedTaskError,
)
from src.uncertainty import StubUncertaintyEstimator, UncertaintyEstimator


bearer_scheme = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


async def get_model_service(request: Request) -> ModelService:
    """Return the model service configured for the current application."""
    return request.app.state.model_service


async def get_extraction_service(request: Request) -> ExtractionService:
    """Return the extraction service configured for the current application."""
    return request.app.state.extraction_service


async def get_task_service(request: Request) -> ExtractionTaskService:
    """Return the extraction task service configured for the application."""
    return request.app.state.task_service


async def get_authenticated_principal(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedPrincipal:
    """Authenticate the request bearer credential through the injected boundary."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedTaskError("Bearer credentials are required")
    try:
        principal = request.app.state.authenticator.authenticate(credentials.credentials)
    except UnauthorizedTaskError:
        raise
    except Exception as error:
        raise UnauthorizedTaskError("Bearer credentials are invalid") from error
    if not principal.owner_id:
        raise UnauthorizedTaskError("Bearer credentials are invalid")
    return principal


def create_app(
    settings: Optional[Settings] = None,
    inference_provider: Optional[InferenceProvider] = None,
    uncertainty_estimator: Optional[UncertaintyEstimator] = None,
    model_catalog: Optional[ModelCatalog] = None,
    authenticator: Optional[BearerAuthenticator] = None,
    task_repository: Optional[TaskRepository] = None,
    task_service: Optional[ExtractionTaskService] = None,
) -> FastAPI:
    """Create a configured HTTP application."""
    application_settings = settings or Settings.from_environment()
    store = ModelStore(
        application_settings.database_path,
        application_settings.data_dir,
        application_settings.max_artifact_size,
    )
    service = ModelService(store)
    extraction_service = ExtractionService(
        inference_provider or StubInferenceProvider(),
        uncertainty_estimator or StubUncertaintyEstimator(),
        model_catalog or StubModelCatalog(),
        application_settings.max_extraction_texts,
        application_settings.max_extraction_characters,
    )
    repository = task_repository or TaskRepository(application_settings.database_path)
    extraction_task_service = task_service or ExtractionTaskService(
        repository,
        extraction_service,
        application_settings.async_extraction_max_texts,
        application_settings.async_extraction_max_characters,
        application_settings.task_retention_seconds,
        application_settings.task_tombstone_seconds,
        application_settings.task_lease_seconds,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Run one bounded durable extraction worker for the application lifetime."""
        stop_event = asyncio.Event()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="extraction-task")
        worker = asyncio.create_task(
            application.state.task_service.worker_loop(
                application.state.settings.task_poll_seconds,
                stop_event,
                executor,
            )
        )
        application.state.task_worker = worker
        try:
            yield
        finally:
            stop_event.set()
            with suppress(asyncio.CancelledError):
                await worker
            executor.shutdown(wait=True)

    application = FastAPI(
        title="Text Extraction and Model Management API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = application_settings
    application.state.model_store = store
    application.state.model_service = service
    application.state.extraction_service = extraction_service
    application.state.task_repository = repository
    application.state.task_service = extraction_task_service
    application.state.authenticator = authenticator or RejectingBearerAuthenticator()

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

    @application.exception_handler(ExtractionRequestError)
    async def handle_extraction_request(
        request: object,
        error: ExtractionRequestError,
    ) -> JSONResponse:
        """Map configured extraction request limits to HTTP 422."""
        return JSONResponse(
            ErrorResponse(detail=str(error), limit=error.limit).model_dump(),
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    @application.exception_handler(ExtractionVolumeError)
    async def handle_extraction_volume(
        request: object,
        error: ExtractionVolumeError,
    ) -> JSONResponse:
        """Map excessive combined source content to HTTP 413."""
        return JSONResponse(
            ErrorResponse(detail=str(error), limit=error.limit).model_dump(),
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )

    @application.exception_handler(UnauthorizedTaskError)
    async def handle_unauthorized_task(request: object, error: UnauthorizedTaskError) -> JSONResponse:
        """Map absent or invalid bearer credentials to HTTP 401."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(),
            status_code=HTTPStatus.UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @application.exception_handler(TaskNotFoundError)
    async def handle_task_not_found(request: object, error: TaskNotFoundError) -> JSONResponse:
        """Map unknown and inaccessible tasks to one HTTP 404 shape."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(),
            status_code=HTTPStatus.NOT_FOUND,
        )

    @application.exception_handler(TaskExpiredError)
    async def handle_task_expired(request: object, error: TaskExpiredError) -> JSONResponse:
        """Map owner-visible retention expiry to HTTP 410."""
        return JSONResponse(
            ErrorResponse(detail=str(error)).model_dump(),
            status_code=HTTPStatus.GONE,
        )

    @application.exception_handler(ResultsPendingError)
    async def handle_results_pending(request: object, error: ResultsPendingError) -> JSONResponse:
        """Map premature result access to HTTP 409 with current status."""
        return JSONResponse(
            ResultsPendingResponse(detail=str(error), status=error.status).model_dump(mode="json"),
            status_code=HTTPStatus.CONFLICT,
        )

    @application.get("/ping")
    async def ping() -> dict[str, str]:
        """Return the service availability payload."""
        return {"message": "pong"}

    @application.post("/entities")
    async def extract_entities(payload: dict[str, str]) -> dict[str, object]:
        """Return the existing mocked extraction response."""
        return {"entities": get_mocked_entities(payload.get("text", ""))}

    @application.post(
        "/extractions",
        response_model=ExtractionResponse,
        responses={
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    async def create_extraction(
        payload: ExtractionRequest,
        extraction_service: ExtractionService = Depends(get_extraction_service),
    ) -> ExtractionResponse:
        """Extract a shared property schema from an ordered batch of texts."""
        return ExtractionResponse.model_validate(extraction_service.extract(payload))

    def validate_task_id(task_id: str) -> str:
        """Normalize a UUID task identifier or use the not-found response."""
        try:
            return str(UUID(task_id))
        except ValueError as error:
            raise TaskNotFoundError("Task was not found") from error

    def task_status_response(task: object) -> TaskStatusResponse:
        """Convert a domain task projection to its safe HTTP representation."""
        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status,
            progress=TaskProgress(
                accepted=task.accepted_count,
                processed=task.processed_count,
                successful=task.successful_count,
                failed=task.failed_count,
            ),
            created_at=task.created_at,
            updated_at=task.updated_at,
            expires_at=task.expires_at,
            error=task.error,
        )

    @application.post(
        "/extraction-tasks",
        response_model=TaskStatusResponse,
        status_code=HTTPStatus.ACCEPTED,
        responses={
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    async def create_extraction_task(
        payload: ExtractionTaskRequest,
        response: Response,
        principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
        service: ExtractionTaskService = Depends(get_task_service),
    ) -> TaskStatusResponse:
        """Durably accept an authenticated extraction batch for later processing."""
        task = service.submit(principal.owner_id, payload)
        response.headers["Location"] = f"/extraction-tasks/{task.task_id}"
        return task_status_response(task)

    @application.get(
        "/extraction-tasks/summary",
        response_model=RunningTaskSummaryResponse,
        responses={401: {"model": ErrorResponse}},
    )
    async def get_running_task_summary(
        principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
        service: ExtractionTaskService = Depends(get_task_service),
    ) -> RunningTaskSummaryResponse:
        """Return owner-scoped aggregate statistics for running extraction tasks."""
        summary = service.get_running_summary(principal.owner_id)
        return RunningTaskSummaryResponse(
            tasks=RunningTaskCounts(
                total=summary["total"],
                queued=summary["queued"],
                processing=summary["processing"],
            ),
            progress=RunningTaskProgress(
                accepted=summary["accepted"],
                processed=summary["processed"],
                successful=summary["successful"],
                failed=summary["failed"],
            ),
        )

    @application.get(
        "/extraction-tasks/{task_id}",
        response_model=TaskStatusResponse,
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            410: {"model": ErrorResponse},
        },
    )
    async def get_extraction_task(
        task_id: str,
        principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
        service: ExtractionTaskService = Depends(get_task_service),
    ) -> TaskStatusResponse:
        """Return owner-scoped task lifecycle and progress."""
        return task_status_response(service.get_status(principal.owner_id, validate_task_id(task_id)))

    @application.get(
        "/extraction-tasks/{task_id}/results",
        response_model=TaskResultsResponse,
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ResultsPendingResponse},
            410: {"model": ErrorResponse},
        },
    )
    async def get_extraction_task_results(
        task_id: str,
        principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
        service: ExtractionTaskService = Depends(get_task_service),
    ) -> TaskResultsResponse:
        """Return complete ordered outcomes for an owned terminal task."""
        result = service.get_results(principal.owner_id, validate_task_id(task_id))
        status = task_status_response(result.task)
        return TaskResultsResponse(
            **status.model_dump(),
            execution_mode=result.execution_mode,
            model=result.model,
            outcomes=result.outcomes,
        )

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

    def custom_openapi() -> dict[str, object]:
        """Publish manual task UUID failures as 404 without a generated 422 response."""
        if application.openapi_schema is None:
            schema = get_openapi(
                title=application.title,
                version=application.version,
                routes=application.routes,
            )
            for path in (
                "/extraction-tasks/{task_id}",
                "/extraction-tasks/{task_id}/results",
            ):
                schema["paths"][path]["get"]["responses"].pop("422", None)
            application.openapi_schema = schema
        return application.openapi_schema

    application.openapi = custom_openapi

    return application


app = create_app()
