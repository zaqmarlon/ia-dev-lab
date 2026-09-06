"""Persistence and concurrency tests for the model store."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from src.model_store import ModelStore
from src.models import DuplicateVersionError, InvalidRegistrationError, LifecycleStatus


class FailingCommitStore(ModelStore):
    """Simulate a catalog failure after final artifact placement."""

    def _commit_registration(self, connection: sqlite3.Connection) -> None:
        """Raise instead of committing a registration transaction."""
        raise sqlite3.OperationalError("simulated commit failure")


class InterruptedStream:
    """Provide one chunk and then simulate an unreadable upload."""

    def __init__(self) -> None:
        """Initialize the stream state."""
        self.read_count = 0

    def read(self, size: int) -> bytes:
        """Return partial bytes once, then fail."""
        self.read_count += 1
        if self.read_count == 1:
            return b"partial"
        raise OSError("interrupted")


class TestModelStore(unittest.TestCase):
    """Verify durable catalog and artifact invariants."""

    def setUp(self) -> None:
        """Create an isolated store for each test."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name)
        self.store = ModelStore(self.data_dir / "catalog.sqlite3", self.data_dir, 1024)

    def tearDown(self) -> None:
        """Remove persisted test data."""
        self.temporary_directory.cleanup()

    def test_registration_persists_digest_artifact_and_immutable_versions(self) -> None:
        """Verify automatic and explicit versions preserve earlier records."""
        first = self.store.register(" Invoice ", BytesIO(b"first"), None, "Purpose", {"a": 1})
        second = self.store.register("invoice", BytesIO(b"second"), None, None, {})
        tenth = self.store.register("INVOICE", BytesIO(b"tenth"), 10, None, {})
        self.assertEqual((first.version, second.version, tenth.version), (1, 2, 10))
        self.assertEqual(self.store.get("invoice", 1), first)
        self.assertEqual(self.store.artifact_path(first.artifact_digest).read_bytes(), b"first")
        self.assertEqual(self.store.get("invoice", 1).metadata, {"a": 1})

    def test_history_is_descending_and_activation_is_atomic(self) -> None:
        """Verify deterministic history and one active version."""
        self.store.register("model", BytesIO(b"one"), None, None, {})
        self.store.register("model", BytesIO(b"two"), None, None, {})
        first = self.store.activate("model", 1)
        second = self.store.activate("model", 2)
        history = self.store.list_versions("model")
        self.assertEqual([item.version for item in history], [2, 1])
        self.assertEqual(first.status, LifecycleStatus.ACTIVE)
        self.assertEqual(second.status, LifecycleStatus.ACTIVE)
        self.assertEqual([item.status for item in history], [LifecycleStatus.ACTIVE, LifecycleStatus.REGISTERED])
        self.assertEqual(len(self.store.activation_history("model")), 2)

    def test_concurrent_explicit_duplicate_has_one_winner(self) -> None:
        """Verify concurrent duplicate registrations cannot both commit."""
        def register(content: bytes) -> str:
            try:
                self.store.register("model", BytesIO(content), 1, None, {})
                return "created"
            except DuplicateVersionError:
                return "duplicate"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(register, (b"one", b"two")))
        self.assertCountEqual(results, ["created", "duplicate"])
        self.assertEqual(len(self.store.list_versions("model")), 1)

    def test_interrupted_write_leaves_no_catalog_or_artifact(self) -> None:
        """Verify unreadable partial content is cleaned up."""
        with self.assertRaises(InvalidRegistrationError):
            self.store.register("model", InterruptedStream(), None, None, {})
        self.assertEqual(list(self.store.artifact_dir.iterdir()), [])

    def test_commit_failure_removes_new_final_artifact(self) -> None:
        """Verify database failure compensates final artifact placement."""
        store = FailingCommitStore(self.data_dir / "failing.sqlite3", self.data_dir / "failing", 1024)
        with self.assertRaises(sqlite3.OperationalError):
            store.register("model", BytesIO(b"content"), None, None, {})
        self.assertEqual(list(store.artifact_dir.iterdir()), [])

    def test_history_of_one_hundred_versions_returns_within_three_seconds(self) -> None:
        """Verify the planned history performance target."""
        for version in range(1, 101):
            self.store.register("model", BytesIO(str(version).encode()), version, None, {})
        started = time.monotonic()
        history = self.store.list_versions("model")
        elapsed = time.monotonic() - started
        self.assertEqual(len(history), 100)
        self.assertLess(elapsed, 3)


if __name__ == "__main__":
    unittest.main()
