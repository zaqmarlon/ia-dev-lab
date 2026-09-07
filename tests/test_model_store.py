"""Integration tests for model registry persistence."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.model_store import ModelStore
from src.models import (
    ArtifactTooLargeError,
    DuplicateVersionError,
    InvalidRegistrationError,
    LifecycleStatus,
    ModelVersionNotFoundError,
)


class TestModelStore(unittest.TestCase):
    """Exercise catalog, artifact, and lifecycle invariants."""

    def setUp(self) -> None:
        """Create isolated storage for each test."""
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "catalog.sqlite3"
        self.store = ModelStore(self.database_path, self.root, 16)

    def tearDown(self) -> None:
        """Remove isolated storage after each test."""
        self.temporary_directory.cleanup()

    def test_persists_versions_and_normalizes_identity(self) -> None:
        """Recover registered data through a recreated store and equivalent name."""
        registered = self.store.register(
            " Extractor ", BytesIO(b"model"), None, "First", {"format": "onnx"}
        )
        recreated = ModelStore(self.database_path, self.root, 16)

        recovered = recreated.get("EXTRACTOR", 1)

        self.assertEqual(recovered, registered)
        self.assertEqual(recovered.model_name, "Extractor")
        self.assertEqual(recovered.description, "First")
        self.assertTrue(recreated.artifact_path(recovered.artifact_digest).is_file())

    def test_assigns_next_version_and_rejects_duplicate(self) -> None:
        """Assign monotonic versions and preserve an explicit version unchanged."""
        first = self.store.register("model", BytesIO(b"one"), 3, None, {})
        second = self.store.register("MODEL", BytesIO(b"two"), None, None, {})

        with self.assertRaises(DuplicateVersionError):
            self.store.register("model", BytesIO(b"replacement"), 3, None, {})

        self.assertEqual((first.version, second.version), (3, 4))
        self.assertEqual(self.store.get("model", 3).artifact_digest, first.artifact_digest)
        self.assertEqual(len(list(self.store.artifact_dir.iterdir())), 2)

    def test_rejects_empty_and_oversized_artifacts_without_files(self) -> None:
        """Remove staged data when artifact validation fails."""
        for content, error_type in (
            (b"", InvalidRegistrationError),
            (b"a" * 17, ArtifactTooLargeError),
        ):
            with self.subTest(size=len(content)), self.assertRaises(error_type):
                self.store.register("model", BytesIO(content), None, None, {})

        self.assertEqual(list(self.store.artifact_dir.iterdir()), [])
        self.assertEqual(list(self.root.glob("upload-*")), [])

    def test_removes_new_artifact_when_commit_fails(self) -> None:
        """Leave no visible record or artifact after a failed transaction."""
        with patch.object(self.store, "_commit_registration", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.store.register("model", BytesIO(b"model"), None, None, {})

        self.assertEqual(list(self.store.artifact_dir.iterdir()), [])
        with self.assertRaises(ModelVersionNotFoundError):
            self.store.get("model", 1)

    def test_lists_history_and_switches_active_version(self) -> None:
        """Order complete history and keep only the selected version active."""
        self.store.register("model", BytesIO(b"one"), 1, None, {})
        self.store.register("model", BytesIO(b"two"), 2, None, {})

        first_active = self.store.activate("model", 1)
        repeated = self.store.activate("model", 1)
        second_active = self.store.activate("model", 2)
        history = self.store.list_versions("model")

        self.assertEqual(first_active.status, LifecycleStatus.ACTIVE)
        self.assertEqual(repeated.status, LifecycleStatus.ACTIVE)
        self.assertEqual(second_active.status, LifecycleStatus.ACTIVE)
        self.assertEqual([item.version for item in history], [2, 1])
        self.assertEqual(
            [item.status for item in history],
            [LifecycleStatus.ACTIVE, LifecycleStatus.REGISTERED],
        )

    def test_missing_records_do_not_change_active_version(self) -> None:
        """Raise for missing records while preserving current lifecycle state."""
        self.store.register("model", BytesIO(b"one"), 1, None, {})
        self.store.activate("model", 1)

        with self.assertRaises(ModelVersionNotFoundError):
            self.store.get("model", 2)
        with self.assertRaises(ModelVersionNotFoundError):
            self.store.list_versions("unknown")
        with self.assertRaises(ModelVersionNotFoundError):
            self.store.activate("model", 2)

        self.assertEqual(self.store.get("model", 1).status, LifecycleStatus.ACTIVE)
