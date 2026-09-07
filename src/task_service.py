"""Authorization and orchestration for asynchronous extraction tasks."""

import asyncio
from concurrent.futures import Executor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Protocol
from uuid import uuid4

from src.extraction import (
    ExecutionMode,
    ExtractionOutcome,
    ExtractionRequestError,
    ExtractionVolumeError,
    InferenceStatus,
    ItemError,
    OutcomeStatus,
    PropertyResult,
    ResolvedModelReference,
    UncertaintyResult,
    UncertaintyStatus,
)
from src.models import ExtractionTaskRecord
from src.schemas import ExtractionTaskRequest
from src.service import ExtractionService
from src.task_repository import TaskRepository


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Represent the opaque owner identity returned by authentication."""

    owner_id: str


class BearerAuthenticator(Protocol):
    """Authenticate a bearer credential without coupling to an identity provider."""

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        """Return the principal associated with a valid bearer token."""
        ...


class RejectingBearerAuthenticator:
    """Reject credentials until a production authenticator is injected."""

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        """Reject an unconfigured authentication attempt."""
        raise UnauthorizedTaskError("Bearer authentication is not configured")


class TaskServiceError(Exception):
    """Provide the base error for extraction task workflows."""


class UnauthorizedTaskError(TaskServiceError):
    """Indicate missing or invalid bearer credentials."""


class TaskNotFoundError(TaskServiceError):
    """Normalize unknown and inaccessible task identifiers."""


class TaskExpiredError(TaskServiceError):
    """Indicate that an owner's task payload exceeded retention."""


class ResultsPendingError(TaskServiceError):
    """Indicate that final results are unavailable for a non-terminal task."""

    def __init__(self, status: str) -> None:
        """Create an error carrying the current task status."""
        self.status = status
        super().__init__("Final task results are not yet available")


@dataclass(frozen=True)
class TaskResultsRecord:
    """Represent a terminal task together with ordered restored outcomes."""

    task: ExtractionTaskRecord
    execution_mode: ExecutionMode
    model: ResolvedModelReference
    outcomes: list[ExtractionOutcome]

    @property
    def status(self):
        """Expose task status for convenient callers."""
        return self.task.status


class ExtractionTaskService:
    """Coordinate durable acceptance, processing, reads, and retention."""

    def __init__(
        self,
        repository: TaskRepository,
        extraction_service: ExtractionService,
        max_texts: int,
        max_characters: int,
        retention_seconds: float,
        tombstone_seconds: float,
        lease_seconds: float,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        """Create a task coordinator with explicit operational limits."""
        self.repository = repository
        self.extraction_service = extraction_service
        self.max_texts = max_texts
        self.max_characters = max_characters
        self.retention_seconds = retention_seconds
        self.tombstone_seconds = tombstone_seconds
        self.lease_seconds = lease_seconds
        self.clock = clock

    def submit(self, owner_id: str, request: ExtractionTaskRequest) -> ExtractionTaskRecord:
        """Validate and durably accept a batch without processing any source."""
        if len(request.texts) > self.max_texts:
            raise ExtractionRequestError(
                f"Text count exceeds the configured limit of {self.max_texts}",
                self.max_texts,
            )
        character_count = sum(len(source.text) for source in request.texts)
        if character_count > self.max_characters:
            raise ExtractionVolumeError(self.max_characters)
        model = self.extraction_service.resolve_model(request)
        now = self.clock()
        criteria = request.schema.model_dump(mode="json")
        model_snapshot = {
            "name": model.name,
            "version": model.version,
            "execution_mode": self.extraction_service.inference_provider.execution_mode.value,
        }
        return self.repository.create_task(
            str(uuid4()),
            owner_id,
            criteria,
            model_snapshot,
            [(source.id, source.text) for source in request.texts],
            now,
            now + timedelta(seconds=self.retention_seconds),
        )

    def get_status(self, owner_id: str, task_id: str) -> ExtractionTaskRecord:
        """Return owner-scoped progress without loading sensitive payloads."""
        self.maintain_retention()
        task = self.repository.get_status(task_id, owner_id)
        if task is None:
            raise TaskNotFoundError("Task was not found")
        if task.is_purged:
            raise TaskExpiredError("Task results have expired")
        return task

    def get_results(self, owner_id: str, task_id: str) -> TaskResultsRecord:
        """Return ordered terminal outcomes for an unexpired owned task."""
        self.maintain_retention()
        task, items = self.repository.get_results(task_id, owner_id)
        if task is None:
            raise TaskNotFoundError("Task was not found")
        if task.is_purged:
            raise TaskExpiredError("Task results have expired")
        if not task.status.is_terminal:
            raise ResultsPendingError(task.status.value)
        if task.model is None:
            raise TaskExpiredError("Task results have expired")
        model = ResolvedModelReference(task.model["name"], task.model["version"])
        outcomes = [self._restore_outcome(item.source_id, item.outcome, item.error) for item in items]
        return TaskResultsRecord(
            task=task,
            execution_mode=ExecutionMode(task.model["execution_mode"]),
            model=model,
            outcomes=outcomes,
        )

    def run_worker_step(self, worker_id: str) -> bool:
        """Claim and process one complete task, preserving committed item outcomes."""
        self.maintain_retention()
        task = self.repository.claim_task(worker_id, self.clock(), self.lease_seconds)
        if task is None:
            return False
        self._process_claimed_task(task, worker_id)
        return True

    def _process_claimed_task(self, task: ExtractionTaskRecord, worker_id: str) -> None:
        """Process a previously leased task through a truthful terminal state."""
        try:
            if task.criteria is None or task.model is None:
                raise RuntimeError("Accepted task snapshot is unavailable")
            property_names = tuple(item["name"] for item in task.criteria["properties"])
            model = ResolvedModelReference(task.model["name"], task.model["version"])
            while True:
                now = self.clock()
                if not self.repository.renew_lease(task.task_id, worker_id, now, self.lease_seconds):
                    raise RuntimeError("Task lease was lost")
                item = self.repository.claim_next_item(task.task_id, worker_id, now)
                if item is None:
                    break
                outcome = self.extraction_service.process_source_with_model(
                    item.source_id,
                    item.source_text or "",
                    property_names,
                    model,
                )
                if outcome.status is OutcomeStatus.COMPLETED:
                    payload = {
                        name: asdict(result)
                        for name, result in outcome.properties.items()
                        if name in property_names
                    }
                    updated = self.repository.finalize_item(
                        task.task_id, worker_id, item.position, payload, None, self.clock()
                    )
                else:
                    failure = outcome.error or ItemError("processing_failed", "Source processing failed")
                    updated = self.repository.finalize_item(
                        task.task_id,
                        worker_id,
                        item.position,
                        None,
                        asdict(failure),
                        self.clock(),
                    )
                if updated.status.is_terminal:
                    break
        except Exception as error:
            detail = str(error) or "Task processing failed"
            try:
                self.repository.fail_task(
                    task.task_id,
                    worker_id,
                    {"code": "task_processing_failed", "detail": detail},
                    self.clock(),
                )
            except ValueError:
                pass

    async def worker_loop(
        self,
        poll_seconds: float,
        stop_event: Optional[asyncio.Event] = None,
        executor: Optional[Executor] = None,
    ) -> None:
        """Continuously execute bounded worker steps until application shutdown."""
        worker_id = str(uuid4())
        shutdown = stop_event or asyncio.Event()
        while not shutdown.is_set():
            self.maintain_retention()
            task = self.repository.claim_task(worker_id, self.clock(), self.lease_seconds)
            if task is None:
                try:
                    await asyncio.wait_for(shutdown.wait(), timeout=poll_seconds)
                except asyncio.TimeoutError:
                    pass
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(executor, self._process_claimed_task, task, worker_id)

    def maintain_retention(self) -> tuple[int, int]:
        """Apply sensitive-payload purge and tombstone deletion policies."""
        return self.repository.maintain_retention(self.clock(), self.tombstone_seconds)

    def _restore_outcome(
        self,
        source_id: str,
        properties: Optional[dict[str, object]],
        error: Optional[dict[str, str]],
    ) -> ExtractionOutcome:
        """Restore canonical persisted JSON into extraction domain values."""
        if error is not None:
            return ExtractionOutcome(
                source_id=source_id,
                status=OutcomeStatus.FAILED,
                error=ItemError(error["code"], error["detail"]),
            )
        restored = {}
        for name, value in (properties or {}).items():
            uncertainty = value["uncertainty"]
            restored[name] = PropertyResult(
                value=value["value"],
                inference_status=InferenceStatus(value["inference_status"]),
                uncertainty=UncertaintyResult(
                    value=uncertainty["value"],
                    status=UncertaintyStatus(uncertainty["status"]),
                ),
            )
        return ExtractionOutcome(
            source_id=source_id,
            status=OutcomeStatus.COMPLETED,
            properties=restored,
        )
