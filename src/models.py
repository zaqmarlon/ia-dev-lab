"""Domain records and errors for the versioned model store."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class LifecycleStatus(str, Enum):
    """Describe whether a version is available or selected."""

    REGISTERED = "registered"
    ACTIVE = "active"


class ExtractionTaskStatus(str, Enum):
    """Enumerate the externally visible task lifecycle states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Return whether this status can no longer transition."""
        return self in {
            self.COMPLETED,
            self.PARTIALLY_COMPLETED,
            self.FAILED,
        }


class ExtractionTaskItemStatus(str, Enum):
    """Enumerate durable item processing states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExtractionTaskRecord:
    """Represent a task projection with lifecycle and optional snapshots."""

    task_id: str
    owner_id: str
    status: ExtractionTaskStatus
    accepted_count: int
    processed_count: int
    successful_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    criteria: Optional[dict[str, Any]] = None
    model: Optional[dict[str, Any]] = None
    error: Optional[dict[str, str]] = None
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    purged_at: Optional[datetime] = None

    @property
    def is_purged(self) -> bool:
        """Return whether sensitive task payloads have expired."""
        return self.purged_at is not None

    def __post_init__(self) -> None:
        """Enforce progress invariants for every loaded task record."""
        if self.accepted_count < 1:
            raise ValueError("accepted_count must be positive")
        if self.successful_count + self.failed_count != self.processed_count:
            raise ValueError("successful and failed counts must equal processed count")
        if not 0 <= self.processed_count <= self.accepted_count:
            raise ValueError("processed count must be within accepted count")
        if self.status.is_terminal and self.processed_count != self.accepted_count:
            raise ValueError("terminal tasks must account for every accepted item")
        if self.status.is_terminal and self.completed_at is None:
            raise ValueError("terminal tasks require a completion time")


@dataclass(frozen=True)
class ExtractionTaskItemRecord:
    """Represent one stored batch item and its optional terminal outcome."""

    task_id: str
    position: int
    source_id: str
    source_text: Optional[str]
    status: ExtractionTaskItemStatus
    outcome: Optional[dict[str, Any]] = None
    error: Optional[dict[str, str]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass(frozen=True)
class Model:
    """Represent a stable model identity."""

    name: str
    description: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class ModelVersion:
    """Represent an immutable registered artifact version."""

    model_name: str
    version: int
    status: LifecycleStatus
    artifact_digest: str
    artifact_size: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: Optional[str] = None


@dataclass(frozen=True)
class ModelArtifact:
    """Represent immutable artifact storage metadata."""

    digest: str
    storage_key: str
    size: int


@dataclass(frozen=True)
class ActivationRecord:
    """Represent a successful active-version change."""

    model_name: str
    version: int
    activated_at: datetime


class ModelStoreError(Exception):
    """Provide the base error for model catalog failures."""


class InvalidRegistrationError(ModelStoreError):
    """Indicate invalid registration input or artifact content."""


class ArtifactTooLargeError(ModelStoreError):
    """Indicate content beyond the configured limit."""

    def __init__(self, limit: int) -> None:
        """Create an error carrying the enforced byte limit."""
        self.limit = limit
        super().__init__(f"Artifact exceeds the configured limit of {limit} bytes")


class DuplicateVersionError(ModelStoreError):
    """Indicate an existing model identity and version pair."""


class ModelVersionNotFoundError(ModelStoreError):
    """Indicate an absent model identity or version."""


class IneligibleVersionError(ModelStoreError):
    """Indicate a version that cannot be activated."""
