"""Application workflows for model registration and lifecycle control."""

import json
from typing import Any, BinaryIO

from src.model_store import ModelStore
from src.models import InvalidRegistrationError, ModelVersion


class ModelService:
    """Validate inputs and coordinate model registry operations."""

    def __init__(self, store: ModelStore) -> None:
        """Create a service backed by the supplied model store."""
        self.store = store

    def register(
        self,
        model_name: str,
        artifact: BinaryIO,
        version: int | None,
        description: str | None,
        metadata: dict[str, Any],
    ) -> ModelVersion:
        """Validate and register one immutable model version."""
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidRegistrationError("Model name is required")
        if version is not None and (
            isinstance(version, bool) or not isinstance(version, int) or version < 1
        ):
            raise InvalidRegistrationError("Version must be a positive integer")
        if not isinstance(metadata, dict):
            raise InvalidRegistrationError("metadata must be a JSON object")
        try:
            json.dumps(metadata)
        except (TypeError, ValueError) as error:
            raise InvalidRegistrationError(
                "metadata must contain JSON-compatible values"
            ) from error
        return self.store.register(
            model_name, artifact, version, description, metadata
        )

    def get(self, model_name: str, version: int) -> ModelVersion:
        """Retrieve one immutable model version."""
        return self.store.get(model_name, version)

    def history(self, model_name: str) -> list[ModelVersion]:
        """Retrieve the complete version history for a model."""
        return self.store.list_versions(model_name)

    def activate(self, model_name: str, version: int) -> ModelVersion:
        """Designate one registered version as active."""
        return self.store.activate(model_name, version)
