"""Contract tests for versioned model HTTP operations."""

from pathlib import Path
import tempfile
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import ASGITestClient


class TestModelsContract(unittest.TestCase):
    """Verify the published paths, payloads, and status codes."""

    def setUp(self) -> None:
        """Create an isolated application for each contract test."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary_directory.name)
        settings = Settings(data_dir, data_dir / "catalog.sqlite3", 8)
        self.client = ASGITestClient(create_app(settings))

    def tearDown(self) -> None:
        """Remove the isolated application data."""
        self.client.close()
        self.temporary_directory.cleanup()

    def test_openapi_exposes_model_operations(self) -> None:
        """Verify every contracted model operation is published."""
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("post", paths["/models/{model_name}/versions"])
        self.assertIn("get", paths["/models/{model_name}/versions"])
        self.assertIn("get", paths["/models/{model_name}/versions/{version}"])
        self.assertIn("post", paths["/models/{model_name}/versions/{version}/activate"])

    def test_registration_and_detail_follow_response_contract(self) -> None:
        """Verify registration and detail responses expose required fields."""
        response = self.client.post(
            "/models/invoice/versions",
            files={"artifact": ("model.bin", b"valid", "application/octet-stream")},
            data={"description": "Invoice model", "metadata": '{"team":"ai"}'},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "model_name", "version", "status", "artifact_digest",
                "artifact_size", "description", "metadata", "created_at",
            },
        )
        detail = self.client.get("/models/invoice/versions/1")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), body)

    def test_history_activation_and_error_statuses_follow_contract(self) -> None:
        """Verify history, activation, absence, conflict, and size responses."""
        first = self.client.post(
            "/models/invoice/versions",
            files={"artifact": ("one.bin", b"one", "application/octet-stream")},
        )
        self.assertEqual(first.status_code, 201)
        duplicate = self.client.post(
            "/models/invoice/versions",
            files={"artifact": ("one.bin", b"one", "application/octet-stream")},
            data={"version": "1"},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("detail", duplicate.json())
        too_large = self.client.post(
            "/models/invoice/versions",
            files={"artifact": ("large.bin", b"123456789", "application/octet-stream")},
        )
        self.assertEqual(too_large.status_code, 413)
        self.assertEqual(too_large.json()["limit"], 8)
        history = self.client.get("/models/invoice/versions")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["model_name"], "invoice")
        activated = self.client.post("/models/invoice/versions/1/activate")
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.json()["status"], "active")
        self.assertEqual(self.client.get("/models/missing/versions").status_code, 404)
        self.assertEqual(self.client.get("/models/invoice/versions/99").status_code, 404)


if __name__ == "__main__":
    unittest.main()
