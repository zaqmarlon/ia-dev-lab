"""Application workflows for model registration and lifecycle control."""

import json
from typing import Any, BinaryIO, Optional

from src.model_store import ModelStore
from src.models import InvalidRegistrationError, ModelVersion


class ModelService:
    """Validate inputs and coordinate model catalog operations."""

    def __init__(self, store: ModelStore) -> None:
        """Create a service backed by the supplied model store."""
        self.store = store

    def register(
        self,
        model_name: str,
        artifact: BinaryIO,
        version: Optional[int],
        description: Optional[str],
        metadata: dict[str, Any],
    ) -> ModelVersion:
        """Validate and register one immutable model version."""
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidRegistrationError("Model name is required")
        if version is not None and (isinstance(version, bool) or version < 1):
            raise InvalidRegistrationError("Version must be a positive integer")
        if not isinstance(metadata, dict):
            raise InvalidRegistrationError("metadata must be a JSON object")
        try:
            json.dumps(metadata)
        except (TypeError, ValueError) as exc:
            raise InvalidRegistrationError("metadata must contain JSON-compatible values") from exc
        return self.store.register(model_name, artifact, version, description, metadata)

    def get(self, model_name: str, version: int) -> ModelVersion:
        """Retrieve one immutable model version."""
        return self.store.get(model_name, version)

    def history(self, model_name: str) -> list[ModelVersion]:
        """Retrieve complete deterministic version history."""
        return self.store.list_versions(model_name)

    def activate(self, model_name: str, version: int) -> ModelVersion:
        """Designate an eligible version for future extraction work."""
        return self.store.activate(model_name, version)

    def resolve(self, model_name: str, version: Optional[int] = None) -> ModelVersion:
        """Resolve a specific or currently active version for extraction."""
        return self.store.resolve(model_name, version)
