"""Contract tests for asynchronous extraction tasks."""

from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from src.app import create_app
from src.settings import Settings
from src.task_service import AuthenticatedPrincipal
from tests.http_client import ASGITestClient


class TestAuthenticator:
    """Authenticate deterministic bearer tokens for HTTP tests."""

    def authenticate(self, token: str) -> AuthenticatedPrincipal:
        """Map a valid token to its owner and reject all other values."""
        if token != "owner-token":
            raise ValueError("Invalid bearer credentials")
        return AuthenticatedPrincipal("owner")


class TestExtractionTasksContract(unittest.TestCase):
    """Verify asynchronous routes and their published response shapes."""

    def setUp(self) -> None:
        """Create an isolated authenticated application."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary_directory.name)
        settings = Settings(data_dir, data_dir / "catalog.sqlite3", task_poll_seconds=60)
        self.application = create_app(settings, authenticator=TestAuthenticator())
        self.client = ASGITestClient(self.application)
        self.headers = {"Authorization": "Bearer owner-token"}

    def tearDown(self) -> None:
        """Remove isolated application data."""
        self.client.close()
        self.temporary_directory.cleanup()

    def payload(self) -> dict[str, object]:
        """Return a minimal valid task submission."""
        return {
            "texts": [{"id": "document-1", "text": "OpenAI is in San Francisco."}],
            "schema": {"properties": [{"name": "organization", "type": "string"}]},
        }

    def test_openapi_publishes_all_task_operations_and_responses(self) -> None:
        """Verify the task API advertises every contracted status code."""
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertEqual(set(paths["/extraction-tasks"]["post"]["responses"]), {"202", "401", "413", "422"})
        self.assertEqual(set(paths["/extraction-tasks/{task_id}"]["get"]["responses"]), {"200", "401", "404", "410"})
        self.assertEqual(set(paths["/extraction-tasks/{task_id}/results"]["get"]["responses"]), {"200", "401", "404", "409", "410"})

    def test_submission_returns_202_location_uuid_and_zero_progress(self) -> None:
        """Verify durable acceptance uses the documented initial representation."""
        response = self.client.post("/extraction-tasks", json=self.payload(), headers=self.headers)
        self.assertEqual(response.status_code, 202)
        body = response.json()
        UUID(body["task_id"])
        self.assertEqual(response.headers["location"], f"/extraction-tasks/{body['task_id']}")
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["progress"], {"accepted": 1, "processed": 0, "successful": 0, "failed": 0})

    def test_authentication_and_submission_errors_use_contract_statuses(self) -> None:
        """Verify credentials, item limits, and volume limits are mapped consistently."""
        self.assertEqual(self.client.post("/extraction-tasks", json=self.payload()).status_code, 401)
        invalid = self.payload()
        invalid["texts"] = []
        self.assertEqual(self.client.post("/extraction-tasks", json=invalid, headers=self.headers).status_code, 422)
        oversized = self.payload()
        oversized["texts"][0]["text"] = "x" * 1_000_001
        self.assertEqual(self.client.post("/extraction-tasks", json=oversized, headers=self.headers).status_code, 413)

    def test_status_and_pending_results_contracts(self) -> None:
        """Verify status omits outcomes and premature results include current state."""
        created = self.client.post("/extraction-tasks", json=self.payload(), headers=self.headers).json()
        task_id = created["task_id"]
        status = self.client.get(f"/extraction-tasks/{task_id}", headers=self.headers)
        self.assertEqual(status.status_code, 200)
        self.assertNotIn("outcomes", status.json())
        pending = self.client.get(f"/extraction-tasks/{task_id}/results", headers=self.headers)
        self.assertEqual(pending.status_code, 409)
        self.assertEqual(pending.json()["status"], "queued")
        self.assertEqual(self.client.get("/extraction-tasks/not-a-uuid", headers=self.headers).status_code, 404)
        unknown = "00000000-0000-4000-8000-000000000000"
        self.assertEqual(self.client.get(f"/extraction-tasks/{unknown}", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get(f"/extraction-tasks/{unknown}/results", headers=self.headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
