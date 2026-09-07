"""Tests for model registry HTTP schemas."""

from datetime import datetime, timezone
import unittest

from src.models import LifecycleStatus, ModelVersion
from src.schemas import ErrorResponse, ModelVersionResponse, parse_metadata


class TestModelSchemas(unittest.TestCase):
    """Exercise response serialization and multipart metadata parsing."""

    def test_serializes_model_version(self) -> None:
        """Convert a domain record into its response representation."""
        record = ModelVersion(
            "model", 1, LifecycleStatus.REGISTERED, "abc", 3,
            {"format": "onnx"}, datetime.now(timezone.utc), "First",
        )

        response = ModelVersionResponse.model_validate(record).model_dump(mode="json")

        self.assertEqual(response["model_name"], "model")
        self.assertEqual(response["status"], "registered")
        self.assertEqual(response["metadata"], {"format": "onnx"})

    def test_parses_optional_metadata(self) -> None:
        """Return an object for absent and valid serialized metadata."""
        self.assertEqual(parse_metadata(None), {})
        self.assertEqual(parse_metadata(""), {})
        self.assertEqual(parse_metadata('{"stage":"candidate"}'), {"stage": "candidate"})

    def test_rejects_malformed_or_non_object_metadata(self) -> None:
        """Reject invalid JSON and valid JSON values that are not objects."""
        for value in ("{invalid", "[]", '"text"'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_metadata(value)

    def test_error_response_exposes_optional_limit(self) -> None:
        """Include an artifact limit when supplied."""
        response = ErrorResponse(detail="too large", limit=10)

        self.assertEqual(response.model_dump(), {"detail": "too large", "limit": 10})
