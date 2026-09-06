"""Domain records and errors for the versioned model store."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class LifecycleStatus(str, Enum):
    """Describe whether a version is available or selected."""

    REGISTERED = "registered"
    ACTIVE = "active"


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
