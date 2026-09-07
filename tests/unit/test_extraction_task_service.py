"""Unit tests for asynchronous extraction task orchestration."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from src.extraction import StubModelCatalog
from src.inference import StubInferenceProvider
from src.schemas import ExtractionTaskRequest
from src.service import ExtractionService
from src.task_repository import TaskRepository
from src.task_service import ResultsPendingError, TaskExpiredError, ExtractionTaskService
from src.uncertainty import StubUncertaintyEstimator


class TestExtractionTaskService(unittest.TestCase):
    """Verify validation, snapshotting, processing, and result access."""

    def setUp(self) -> None:
        """Create a deterministic service with isolated persistence."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = TaskRepository(Path(self.temporary_directory.name) / "tasks.sqlite3")
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        extraction = ExtractionService(StubInferenceProvider(("bad",)), StubUncertaintyEstimator(), StubModelCatalog(), 10, 1000)
        self.service = ExtractionTaskService(self.repository, extraction, 100, 1_000_000, 60, 60, 30, clock=lambda: self.now)

    def tearDown(self) -> None:
        """Remove isolated persistence."""
        self.temporary_directory.cleanup()

    def request(self, *source_ids: str) -> ExtractionTaskRequest:
        """Build a valid request for the provided source IDs."""
        return ExtractionTaskRequest.model_validate({
            "texts": [{"id": source_id, "text": "content"} for source_id in source_ids],
            "schema": {"properties": [{"name": "organization", "type": "string"}]},
        })

    def test_submission_is_non_blocking_prevalidated_and_snapshotted(self) -> None:
        """Verify acceptance persists immutable criteria and resolved model data."""
        status = self.service.submit("owner", self.request("first", "second"))
        self.assertEqual(status.status.value, "queued")
        self.assertEqual(status.processed_count, 0)
        claimed = self.repository.claim_task("inspect", self.now, 30)
        self.assertEqual(claimed.criteria["properties"][0]["name"], "organization")
        self.assertEqual(claimed.model["name"], "stub-extraction-provider")

    def test_async_limit_accepts_more_than_the_synchronous_limit(self) -> None:
        """Verify asynchronous batches retain their independent 100-item default."""
        task = self.service.submit("owner", self.request(*[f"source-{index}" for index in range(11)]))
        self.assertEqual(task.accepted_count, 11)

    def test_worker_isolates_failures_and_returns_repeatable_partial_results(self) -> None:
        """Verify per-item work preserves successes and terminal result reads."""
        task = self.service.submit("owner", self.request("first", "bad", "third"))
        self.assertTrue(self.service.run_worker_step("worker"))
        first = self.service.get_results("owner", task.task_id)
        second = self.service.get_results("owner", task.task_id)
        self.assertEqual(first.status.value, "partially_completed")
        self.assertEqual([item.source_id for item in first.outcomes], ["first", "bad", "third"])
        self.assertEqual(first, second)

    def test_task_level_failure_finalizes_every_remaining_item(self) -> None:
        """Verify an invalid durable snapshot becomes one actionable failed task."""
        self.repository.create_task(
            "broken-task",
            "owner",
            {},
            {"name": "stub", "version": "1", "execution_mode": "stub"},
            [("first", "content"), ("second", "content")],
            self.now,
            self.now + timedelta(seconds=60),
        )
        self.assertTrue(self.service.run_worker_step("worker"))
        result = self.service.get_results("owner", "broken-task")
        self.assertEqual(result.status.value, "failed")
        self.assertEqual(result.task.failed_count, 2)
        self.assertTrue(all(item.error.code == "task_processing_failed" for item in result.outcomes))

    def test_results_are_pending_before_terminal_and_expired_after_retention(self) -> None:
        """Verify result availability follows lifecycle and retention boundaries."""
        task = self.service.submit("owner", self.request("first"))
        with self.assertRaises(ResultsPendingError):
            self.service.get_results("owner", task.task_id)
        self.service.run_worker_step("worker")
        self.now += timedelta(seconds=61)
        self.service.maintain_retention()
        with self.assertRaises(TaskExpiredError):
            self.service.get_results("owner", task.task_id)


if __name__ == "__main__":
    unittest.main()
