"""Integration tests for the asynchronous extraction task lifecycle."""

import asyncio
from pathlib import Path
import tempfile
import unittest

import httpx

from src.app import create_app
from src.inference import StubInferenceProvider
from src.settings import Settings
from src.task_service import AuthenticatedPrincipal
from tests.http_client import ASGITestClient


class OwnerAuthenticator:
    """Treat each non-empty test token as a distinct authenticated owner."""

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        """Return a principal derived from the test token."""
        if not token:
            raise ValueError("Invalid bearer credentials")
        return AuthenticatedPrincipal(token)


class TestExtractionTasksEndpoint(unittest.TestCase):
    """Verify acceptance, worker progress, ownership, and final results."""

    def setUp(self) -> None:
        """Create an isolated application with deterministic failures."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary_directory.name)
        settings = Settings(data_dir, data_dir / "catalog.sqlite3", task_poll_seconds=60)
        self.application = create_app(settings, inference_provider=StubInferenceProvider(("bad",)), authenticator=OwnerAuthenticator())
        self.client = ASGITestClient(self.application)
        self.owner = {"Authorization": "Bearer owner"}
        self.other = {"Authorization": "Bearer other"}

    def tearDown(self) -> None:
        """Remove isolated application data."""
        self.client.close()
        self.temporary_directory.cleanup()

    def payload(self, *source_ids: str) -> dict[str, object]:
        """Build a valid ordered batch."""
        return {
            "texts": [{"id": source_id, "text": "same text"} for source_id in source_ids],
            "schema": {"properties": [{"name": "organization", "type": "string"}]},
        }

    def test_submission_precedes_processing_and_invalid_input_creates_no_task(self) -> None:
        """Verify HTTP acceptance is durable without invoking worker processing."""
        response = self.client.post("/extraction-tasks", json=self.payload("first"), headers=self.owner)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        invalid = self.client.post("/extraction-tasks", json=self.payload("same", "same"), headers=self.owner)
        self.assertEqual(invalid.status_code, 422)

    def test_summary_returns_owner_scoped_running_task_statistics(self) -> None:
        """Verify running task statistics aggregate queued and processing work for one owner."""
        self.client.post(
            "/extraction-tasks", json=self.payload("first", "second"), headers=self.owner
        )
        self.client.post("/extraction-tasks", json=self.payload("other"), headers=self.other)
        self.application.state.task_repository.claim_task(
            "test-worker",
            self.application.state.task_service.clock(),
            self.application.state.task_service.lease_seconds,
        )

        response = self.client.get("/extraction-tasks/summary", headers=self.owner)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "running",
                "tasks": {"total": 1, "queued": 0, "processing": 1},
                "progress": {"accepted": 2, "processed": 0, "successful": 0, "failed": 0},
            },
        )

    def test_polling_and_results_preserve_order_partial_success_and_owner_isolation(self) -> None:
        """Verify the complete mixed-outcome HTTP journey."""
        created = self.client.post("/extraction-tasks", json=self.payload("first", "bad", "third"), headers=self.owner).json()
        task_id = created["task_id"]
        self.assertEqual(self.client.get(f"/extraction-tasks/{task_id}/results", headers=self.owner).status_code, 409)
        self.assertTrue(self.application.state.task_service.run_worker_step("test-worker"))
        status = self.client.get(f"/extraction-tasks/{task_id}", headers=self.owner)
        self.assertEqual(status.json()["progress"], {"accepted": 3, "processed": 3, "successful": 2, "failed": 1})
        self.assertNotIn("outcomes", status.json())
        result = self.client.get(f"/extraction-tasks/{task_id}/results", headers=self.owner)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "partially_completed")
        self.assertEqual([item["source_id"] for item in result.json()["outcomes"]], ["first", "bad", "third"])
        self.assertEqual(self.client.get(f"/extraction-tasks/{task_id}", headers=self.other).status_code, 404)
        self.assertEqual(self.client.get("/extraction-tasks/00000000-0000-4000-8000-000000000000", headers=self.owner).status_code, 404)

    def test_application_lifespan_worker_processes_an_accepted_batch(self) -> None:
        """Verify the application-managed worker advances accepted work."""
        self.application.state.settings = Settings(
            self.application.state.settings.data_dir,
            self.application.state.settings.database_path,
            task_poll_seconds=0.01,
        )

        async def exercise() -> None:
            """Submit and poll while the application lifespan is active."""
            async with self.application.router.lifespan_context(self.application):
                transport = httpx.ASGITransport(app=self.application)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    created = await client.post(
                        "/extraction-tasks",
                        json=self.payload("lifespan-source"),
                        headers=self.owner,
                    )
                    task_id = created.json()["task_id"]
                    for _ in range(100):
                        status = await client.get(f"/extraction-tasks/{task_id}", headers=self.owner)
                        if status.json()["status"] == "completed":
                            return
                        await asyncio.sleep(0.01)
                    self.fail("The lifespan worker did not complete the accepted task")

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
