"""Domain records and errors for the versioned model registry."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LifecycleStatus(str, Enum):
    """Describe the lifecycle state of a model version."""

    REGISTERED = "registered"
    ACTIVE = "active"


@dataclass(frozen=True)
class ModelVersion:
    """Represent one immutable registered model artifact version."""

    model_name: str
    version: int
    status: LifecycleStatus
    artifact_digest: str
    artifact_size: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str | None = None


class ModelRegistryError(Exception):
    """Provide the base error for model registry operations."""


class InvalidRegistrationError(ModelRegistryError):
    """Indicate invalid registration input or artifact content."""


class ArtifactTooLargeError(ModelRegistryError):
    """Indicate content beyond the configured upload limit."""

    def __init__(self, limit: int) -> None:
        """Create an error containing the enforced byte limit."""
        self.limit = limit
        super().__init__(f"Artifact exceeds the configured limit of {limit} bytes")


class DuplicateVersionError(ModelRegistryError):
    """Indicate an existing model identity and version pair."""


class ModelVersionNotFoundError(ModelRegistryError):
    """Indicate an absent model identity or version."""
