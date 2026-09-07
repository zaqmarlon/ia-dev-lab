"""Unit tests for durable asynchronous task persistence."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from typing import Optional

from src.models import ExtractionTaskStatus
from src.task_repository import TaskRepository


class TestTaskRepository(unittest.TestCase):
    """Verify transactions, leases, progress, ordering, and retention."""

    def setUp(self) -> None:
        """Create an isolated SQLite repository."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "tasks.sqlite3"
        self.repository = TaskRepository(self.database_path)
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        """Remove the isolated database."""
        self.temporary_directory.cleanup()

    def create_task(self, task_id: str = "task-1", expires_at: Optional[datetime] = None) -> None:
        """Persist a two-item task with duplicate text."""
        self.repository.create_task(
            task_id,
            "owner",
            {"properties": [{"name": "organization", "type": "string"}]},
            {"name": "stub", "version": "1", "execution_mode": "stub"},
            [("first", "same"), ("second", "same")],
            self.now,
            expires_at or self.now + timedelta(days=1),
        )

    def test_creation_is_atomic_unique_and_survives_restart(self) -> None:
        """Verify task items commit together and duplicate source IDs roll back."""
        self.create_task()
        reopened = TaskRepository(self.database_path)
        self.assertEqual(reopened.get_status("task-1", "owner").accepted_count, 2)
        with self.assertRaises(ValueError):
            reopened.create_task(
                "bad", "owner", {}, {}, [("same", "a"), ("same", "b")],
                self.now, self.now + timedelta(days=1),
            )
        self.assertIsNone(reopened.get_status("bad", "owner"))

    def test_leases_are_exclusive_recoverable_and_skip_terminal_items(self) -> None:
        """Verify expired work can resume without selecting completed items."""
        self.create_task()
        lease = self.repository.claim_task("worker-1", self.now, 10)
        self.assertEqual(lease.task_id, "task-1")
        self.assertIsNone(self.repository.claim_task("worker-2", self.now, 10))
        first = self.repository.claim_next_item("task-1", "worker-1", self.now)
        self.repository.finalize_item("task-1", "worker-1", first.position, {"organization": {}}, None, self.now)
        recovered = self.repository.claim_task("worker-2", self.now + timedelta(seconds=11), 10)
        self.assertEqual(recovered.task_id, "task-1")
        self.assertEqual(self.repository.claim_next_item("task-1", "worker-2", self.now).source_id, "second")

    def test_progress_is_monotonic_and_terminal_state_is_immutable(self) -> None:
        """Verify item finalization maintains counters and terminal derivation."""
        self.create_task()
        self.repository.claim_task("worker", self.now, 30)
        for expected, error in (("first", None), ("second", {"code": "failed", "detail": "bad"})):
            item = self.repository.claim_next_item("task-1", "worker", self.now)
            self.assertEqual(item.source_id, expected)
            self.repository.finalize_item("task-1", "worker", item.position, {} if error is None else None, error, self.now)
        status = self.repository.get_status("task-1", "owner")
        self.assertEqual(status.status, ExtractionTaskStatus.PARTIALLY_COMPLETED)
        self.assertEqual((status.processed_count, status.successful_count, status.failed_count), (2, 1, 1))
        self.assertIsNone(self.repository.claim_task("another", self.now, 30))

    def test_results_are_ordered_and_retention_creates_then_deletes_tombstone(self) -> None:
        """Verify ordered outcomes, sensitive purge, and final tombstone deletion."""
        self.create_task(expires_at=self.now + timedelta(seconds=1))
        self.repository.claim_task("worker", self.now, 30)
        for _ in range(2):
            item = self.repository.claim_next_item("task-1", "worker", self.now)
            self.repository.finalize_item("task-1", "worker", item.position, {"value": {"value": None}}, None, self.now)
        self.assertEqual([item.source_id for item in self.repository.get_results("task-1", "owner")[1]], ["first", "second"])
        self.repository.maintain_retention(self.now + timedelta(seconds=2), 10)
        self.assertTrue(self.repository.get_status("task-1", "owner").is_purged)
        self.assertEqual(self.repository.get_results("task-1", "owner")[1], [])
        self.repository.maintain_retention(self.now + timedelta(seconds=12), 10)
        self.assertIsNone(self.repository.get_status("task-1", "owner"))


if __name__ == "__main__":
    unittest.main()
