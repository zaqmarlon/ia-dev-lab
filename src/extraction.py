"""Domain types and boundaries for schema-driven extraction."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol


class ExecutionMode(str, Enum):
    """Describe whether extraction used a stub or production model."""

    STUB = "stub"
    MODEL = "model"


class OutcomeStatus(str, Enum):
    """Describe the processing state of one source text."""

    COMPLETED = "completed"
    FAILED = "failed"


class InferenceStatus(str, Enum):
    """Describe the availability of one inferred property."""

    INFERRED = "inferred"
    NOT_FOUND = "not_found"
    NOT_INFERRED = "not_inferred"


class UncertaintyStatus(str, Enum):
    """Describe the availability of an uncertainty measurement."""

    CALCULATED = "calculated"
    NOT_CALCULATED = "not_calculated"


@dataclass(frozen=True)
class ResolvedModelReference:
    """Identify the model or stub selected for an extraction."""

    name: str
    version: str


@dataclass(frozen=True)
class UncertaintyResult:
    """Represent uncertainty for one property value."""

    value: Optional[float]
    status: UncertaintyStatus


@dataclass(frozen=True)
class PropertyResult:
    """Represent the inferred value and uncertainty for one property."""

    value: Any
    inference_status: InferenceStatus
    uncertainty: UncertaintyResult


@dataclass(frozen=True)
class ItemError:
    """Describe a failure isolated to one source text."""

    code: str
    detail: str


@dataclass(frozen=True)
class ExtractionOutcome:
    """Represent the completed or failed result for one source text."""

    source_id: str
    status: OutcomeStatus
    properties: dict[str, PropertyResult] = field(default_factory=dict)
    error: Optional[ItemError] = None


@dataclass(frozen=True)
class ExtractionResult:
    """Represent the ordered result of a batch extraction."""

    execution_mode: ExecutionMode
    model: ResolvedModelReference
    outcomes: list[ExtractionOutcome]


class ExtractionError(Exception):
    """Provide the base error for batch-level extraction failures."""


class ExtractionRequestError(ExtractionError):
    """Indicate a structurally valid payload outside configured limits."""

    def __init__(self, detail: str, limit: Optional[int] = None) -> None:
        """Create an actionable request error with an optional limit."""
        self.limit = limit
        super().__init__(detail)


class ExtractionVolumeError(ExtractionRequestError):
    """Indicate combined source content beyond the configured limit."""

    def __init__(self, limit: int) -> None:
        """Create an error carrying the character limit."""
        super().__init__(
            f"Combined text content exceeds the configured limit of {limit} characters",
            limit,
        )


class ModelCatalog(Protocol):
    """Resolve requested model metadata without coupling to its storage."""

    def resolve(self, name: Optional[str], version: Optional[str]) -> ResolvedModelReference:
        """Return the model reference selected for an extraction."""
        ...


class StubModelCatalog:
    """Resolve every request to an explicit non-production model reference."""

    def resolve(self, name: Optional[str], version: Optional[str]) -> ResolvedModelReference:
        """Return a stable reference that makes stub execution unmistakable."""
        return ResolvedModelReference(name or "stub-extraction-provider", version or "stub")
