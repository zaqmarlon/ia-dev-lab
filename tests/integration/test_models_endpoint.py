"""HTTP integration tests for model lifecycle routes."""

from pathlib import Path
import tempfile
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import ASGITestClient


class TestModelsEndpoint(unittest.TestCase):
    """Verify end-to-end model management journeys."""

    def setUp(self) -> None:
        """Create an isolated HTTP application."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary_directory.name)
        self.client = ASGITestClient(
            create_app(Settings(data_dir, data_dir / "catalog.sqlite3", 5))
        )

    def tearDown(self) -> None:
        """Close the client and remove its data."""
        self.client.close()
        self.temporary_directory.cleanup()

    def register(self, content: bytes, **fields: str) -> object:
        """Submit a multipart registration request."""
        return self.client.post(
            "/models/sample/versions",
            files={"artifact": ("model.bin", content, "application/octet-stream")},
            data=fields,
        )

    def test_register_retrieve_list_and_switch_active_version(self) -> None:
        """Verify the complete successful HTTP journey."""
        first = self.register(b"one", description="Sample", metadata='{"kind":"stub"}')
        second = self.register(b"two")
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(self.client.get("/models/sample/versions/1").json(), first.json())
        history = self.client.get("/models/sample/versions").json()["versions"]
        self.assertEqual([item["version"] for item in history], [2, 1])
        self.assertEqual(self.client.post("/models/sample/versions/1/activate").status_code, 200)
        self.assertEqual(self.client.post("/models/sample/versions/2/activate").status_code, 200)
        statuses = [item["status"] for item in self.client.get("/models/sample/versions").json()["versions"]]
        self.assertEqual(statuses, ["active", "registered"])

    def test_invalid_registrations_return_actionable_errors_without_changes(self) -> None:
        """Verify malformed, duplicate, empty, and oversized requests are atomic."""
        self.assertEqual(self.register(b"one", version="1").status_code, 201)
        self.assertEqual(self.register(b"two", version="1").status_code, 409)
        self.assertEqual(self.register(b"").status_code, 422)
        oversized = self.register(b"123456")
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(oversized.json()["limit"], 5)
        malformed = self.register(b"two", metadata="[]")
        self.assertEqual(malformed.status_code, 422)
        versions = self.client.get("/models/sample/versions").json()["versions"]
        self.assertEqual([item["version"] for item in versions], [1])


if __name__ == "__main__":
    unittest.main()
