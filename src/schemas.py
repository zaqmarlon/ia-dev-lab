"""Request and response schemas for the HTTP API."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models import LifecycleStatus


EntityItem = dict[str, object]


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
