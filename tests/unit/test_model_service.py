"""Unit tests for model lifecycle workflows."""

from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from src.model_service import ModelService
from src.model_store import ModelStore
from src.models import ArtifactTooLargeError, InvalidRegistrationError, ModelVersionNotFoundError


class TestModelService(unittest.TestCase):
    """Verify validation and resolution behavior."""

    def setUp(self) -> None:
        """Create an isolated service for each test."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary_directory.name)
        self.service = ModelService(ModelStore(data_dir / "catalog.sqlite3", data_dir, 5))

    def tearDown(self) -> None:
        """Remove persisted test data."""
        self.temporary_directory.cleanup()

    def test_validation_rejects_blank_name_nonpositive_version_and_bad_metadata(self) -> None:
        """Verify transient registration input validation."""
        with self.assertRaises(InvalidRegistrationError):
            self.service.register(" ", BytesIO(b"ok"), None, None, {})
        with self.assertRaises(InvalidRegistrationError):
            self.service.register("model", BytesIO(b"ok"), 0, None, {})
        with self.assertRaises(InvalidRegistrationError):
            self.service.register("model", BytesIO(b"ok"), None, None, [])

    def test_empty_and_size_boundary_validation(self) -> None:
        """Verify empty and oversized content while accepting the exact limit."""
        with self.assertRaises(InvalidRegistrationError):
            self.service.register("empty", BytesIO(b""), None, None, {})
        accepted = self.service.register("exact", BytesIO(b"12345"), None, None, {})
        self.assertEqual(accepted.artifact_size, 5)
        with self.assertRaises(ArtifactTooLargeError) as raised:
            self.service.register("large", BytesIO(b"123456"), None, None, {})
        self.assertEqual(raised.exception.limit, 5)

    def test_history_activation_and_resolution(self) -> None:
        """Verify active and explicit version resolution remains traceable."""
        first = self.service.register("model", BytesIO(b"one"), None, None, {})
        self.service.register("model", BytesIO(b"two"), None, None, {})
        with self.assertRaises(ModelVersionNotFoundError):
            self.service.resolve("model")
        selected = self.service.activate("model", 1)
        self.assertEqual(self.service.resolve("model"), selected)
        self.service.activate("model", 2)
        self.assertEqual(self.service.resolve("model", first.version).version, 1)
        self.assertEqual([item.version for item in self.service.history("model")], [2, 1])


if __name__ == "__main__":
    unittest.main()
