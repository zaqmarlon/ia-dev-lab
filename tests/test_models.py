"""Tests for model registry domain types."""

from datetime import datetime, timezone
import unittest

from src.models import ArtifactTooLargeError, LifecycleStatus, ModelVersion


class TestModelDomain(unittest.TestCase):
    """Exercise public domain values and error details."""

    def test_exposes_lifecycle_values(self) -> None:
        """Expose stable registered and active status values."""
        self.assertEqual(LifecycleStatus.REGISTERED.value, "registered")
        self.assertEqual(LifecycleStatus.ACTIVE.value, "active")

    def test_model_version_preserves_public_fields(self) -> None:
        """Preserve all response-facing version data."""
        created_at = datetime.now(timezone.utc)
        version = ModelVersion(
            "extractor", 2, LifecycleStatus.REGISTERED, "digest", 10,
            {"format": "onnx"}, created_at, "Candidate",
        )

        self.assertEqual(version.model_name, "extractor")
        self.assertEqual(version.version, 2)
        self.assertEqual(version.metadata, {"format": "onnx"})
        self.assertEqual(version.created_at, created_at)
        self.assertEqual(version.description, "Candidate")

    def test_artifact_limit_error_exposes_limit(self) -> None:
        """Expose the configured limit for an HTTP error response."""
        error = ArtifactTooLargeError(1024)

        self.assertEqual(error.limit, 1024)
        self.assertIn("1024", str(error))
