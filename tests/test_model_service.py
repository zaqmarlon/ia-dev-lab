"""Unit tests for model registry workflows."""

from io import BytesIO
import unittest
from unittest.mock import Mock

from src.model_service import ModelService
from src.models import InvalidRegistrationError


class TestModelService(unittest.TestCase):
    """Exercise validation and store delegation."""

    def setUp(self) -> None:
        """Create a service with an observable store."""
        self.store = Mock()
        self.service = ModelService(self.store)

    def test_registers_valid_input(self) -> None:
        """Delegate a valid registration unchanged."""
        artifact = BytesIO(b"model")
        expected = object()
        self.store.register.return_value = expected

        result = self.service.register(
            "model", artifact, 2, "Candidate", {"format": "onnx"}
        )

        self.assertIs(result, expected)
        self.store.register.assert_called_once_with(
            "model", artifact, 2, "Candidate", {"format": "onnx"}
        )

    def test_rejects_invalid_registration_values(self) -> None:
        """Reject invalid identity, version, and metadata before persistence."""
        cases = [
            ("", 1, {}),
            ("model", 0, {}),
            ("model", True, {}),
            ("model", 1, []),
            ("model", 1, {"invalid": object()}),
        ]
        for model_name, version, metadata in cases:
            with self.subTest(model_name=model_name, version=version, metadata=metadata):
                with self.assertRaises(InvalidRegistrationError):
                    self.service.register(
                        model_name, BytesIO(b"model"), version, None, metadata
                    )

        self.store.register.assert_not_called()

    def test_delegates_lifecycle_queries(self) -> None:
        """Delegate retrieval, history, and activation to persistence."""
        self.service.get("model", 2)
        self.service.history("model")
        self.service.activate("model", 2)

        self.store.get.assert_called_once_with("model", 2)
        self.store.list_versions.assert_called_once_with("model")
        self.store.activate.assert_called_once_with("model", 2)
