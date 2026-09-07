"""Request and response schemas for the HTTP API."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import warnings
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.extraction import ExecutionMode, InferenceStatus, OutcomeStatus, UncertaintyStatus
from src.models import ExtractionTaskStatus, LifecycleStatus


EntityItem = dict[str, object]


class PropertyType(str, Enum):
    """Enumerate property types supported by the extraction contract."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    STRING_LIST = "string_list"


class SourceText(BaseModel):
    """Validate one identified source text."""

    id: str
    text: str

    @field_validator("id", "text")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        """Normalize and reject blank source fields."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class PropertyDefinition(BaseModel):
    """Validate one requested extraction property."""

    name: str
    type: PropertyType
    required: bool = False
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def require_non_blank_name(cls, value: str) -> str:
        """Normalize and reject a blank property name."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("property name must not be blank")
        return normalized


class ExtractionSchema(BaseModel):
    """Validate the shared property schema for a batch."""

    properties: list[PropertyDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_names(self) -> "ExtractionSchema":
        """Reject duplicate case-sensitive property names."""
        names = [property_definition.name for property_definition in self.properties]
        if len(names) != len(set(names)):
            raise ValueError("property names must be unique")
        return self


class ModelSelection(BaseModel):
    """Validate an optional requested model selection."""

    name: str
    version: Optional[str] = None

    @field_validator("name")
    @classmethod
    def require_non_blank_name(cls, value: str) -> str:
        """Normalize and reject a blank model name."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("model name must not be blank")
        return normalized


with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message='Field name "schema".*')

    class ExtractionRequest(BaseModel):
        """Validate a synchronous schema-driven batch request."""

        texts: list[SourceText] = Field(min_length=1, max_length=10)
        schema: ExtractionSchema
        model: Optional[ModelSelection] = None

        @model_validator(mode="after")
        def require_unique_source_ids(self) -> "ExtractionRequest":
            """Reject duplicate source identifiers while allowing duplicate content."""
            identifiers = [source.id for source in self.texts]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError("source identifiers must be unique")
            return self

    class ExtractionTaskRequest(BaseModel):
        """Validate a complete asynchronous extraction batch."""

        texts: list[SourceText] = Field(min_length=1, max_length=100)
        schema: ExtractionSchema
        model: Optional[ModelSelection] = None

        @model_validator(mode="after")
        def require_unique_source_ids(self) -> "ExtractionTaskRequest":
            """Reject duplicate source identifiers before task persistence."""
            identifiers = [source.id for source in self.texts]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError("source identifiers must be unique")
            return self


class ResolvedModelReference(BaseModel):
    """Serialize the model or stub selected for execution."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    version: str


class UncertaintyResult(BaseModel):
    """Serialize uncertainty for one extracted property."""

    model_config = ConfigDict(from_attributes=True)

    value: Optional[float] = Field(default=None, ge=0, le=1)
    status: UncertaintyStatus


class PropertyResult(BaseModel):
    """Serialize one requested property's result."""

    model_config = ConfigDict(from_attributes=True)

    value: Any
    inference_status: InferenceStatus
    uncertainty: UncertaintyResult


class ItemError(BaseModel):
    """Serialize an item-level processing failure."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    detail: str


class ExtractionOutcome(BaseModel):
    """Serialize one ordered source outcome."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    status: OutcomeStatus
    properties: dict[str, PropertyResult]
    error: Optional[ItemError] = None


class ExtractionResponse(BaseModel):
    """Serialize a complete batch extraction result."""

    model_config = ConfigDict(from_attributes=True)

    execution_mode: ExecutionMode
    model: ResolvedModelReference
    outcomes: list[ExtractionOutcome]


class TaskProgress(BaseModel):
    """Serialize monotonic task item counters."""

    accepted: int = Field(ge=1)
    processed: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)


class TaskStatusResponse(BaseModel):
    """Serialize task lifecycle without sensitive request or result data."""

    task_id: UUID
    status: ExtractionTaskStatus
    progress: TaskProgress
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    error: Optional[ItemError] = None


class TaskResultsResponse(TaskStatusResponse):
    """Serialize the complete ordered outcomes for a terminal task."""

    execution_mode: ExecutionMode
    model: ResolvedModelReference
    outcomes: list[ExtractionOutcome]


class ResultsPendingResponse(BaseModel):
    """Serialize rejection of a non-terminal result request."""

    detail: str
    status: ExtractionTaskStatus


class ModelVersionResponse(BaseModel):
    """Serialize a registered model version."""

    model_config = ConfigDict(from_attributes=True)

    model_name: str
    version: int = Field(ge=1)
    status: LifecycleStatus
    artifact_digest: str
    artifact_size: int = Field(ge=1)
    description: Optional[str] = None
    metadata: dict[str, Any]
    created_at: datetime


class ModelVersionHistoryResponse(BaseModel):
    """Serialize the complete history for one model."""

    model_name: str
    versions: list[ModelVersionResponse]


class ErrorResponse(BaseModel):
    """Serialize an actionable API error."""

    detail: str
    limit: Optional[int] = None


def parse_metadata(value: Optional[str]) -> dict[str, Any]:
    """Parse optional JSON object metadata from a multipart field."""
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("metadata must be a valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata must be a JSON object")
    return parsed
