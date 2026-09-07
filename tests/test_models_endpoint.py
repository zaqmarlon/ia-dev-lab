"""Contract tests for model registry endpoints."""

from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import HttpClient


class TestModelsEndpoint(unittest.TestCase):
    """Exercise model registration, retrieval, history, and activation contracts."""

    def setUp(self) -> None:
        """Create an application with isolated persistent storage."""
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        settings = Settings(self.root, self.root / "catalog.sqlite3", 16)
        self.client = HttpClient(create_app(settings=settings))

    def tearDown(self) -> None:
        """Close the client and remove isolated storage."""
        self.client.close()
        self.temporary_directory.cleanup()

    def test_exposes_expected_model_paths(self) -> None:
        """Publish all planned operations in the OpenAPI contract."""
        paths = self.client.get("/openapi.json").json()["paths"]

        self.assertIn("/models/{model_name}/versions", paths)
        self.assertIn("/models/{model_name}/versions/{version}", paths)
        self.assertIn("/models/{model_name}/versions/{version}/activate", paths)
        self.assertIn("post", paths["/models/{model_name}/versions"])
        self.assertIn("get", paths["/models/{model_name}/versions"])

    def test_registers_and_retrieves_explicit_version(self) -> None:
        """Return the complete representation for a valid multipart registration."""
        response = self._register(
            "Extractor", b"model", version="3", description="Candidate",
            metadata='{"format":"onnx"}',
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        body = response.json()
        self.assertEqual(body["model_name"], "Extractor")
        self.assertEqual(body["version"], 3)
        self.assertEqual(body["status"], "registered")
        self.assertEqual(body["description"], "Candidate")
        self.assertEqual(body["metadata"], {"format": "onnx"})
        self.assertEqual(body["artifact_size"], 5)
        self.assertEqual(len(body["artifact_digest"]), 64)
        self.assertIn("created_at", body)

        retrieved = self.client.get("/models/extractor/versions/3")
        self.assertEqual(retrieved.status_code, HTTPStatus.OK)
        self.assertEqual(retrieved.json(), body)

    def test_assigns_versions_and_returns_descending_history(self) -> None:
        """Assign the next version under a normalized identity and order history."""
        self._register("Model", b"one")
        self._register("MODEL", b"two")

        response = self.client.get("/models/model/versions")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["model_name"], "Model")
        self.assertEqual(
            [item["version"] for item in response.json()["versions"]], [2, 1]
        )

    def test_activates_only_one_version(self) -> None:
        """Replace the active version atomically and allow reactivation."""
        self._register("model", b"one", version="1")
        self._register("model", b"two", version="2")

        self.assertEqual(
            self.client.post("/models/model/versions/1/activate").json()["status"],
            "active",
        )
        self.assertEqual(
            self.client.post("/models/model/versions/1/activate").status_code,
            HTTPStatus.OK,
        )
        self.client.post("/models/model/versions/2/activate")
        history = self.client.get("/models/model/versions").json()["versions"]

        self.assertEqual([item["status"] for item in history], ["active", "registered"])

    def test_maps_invalid_registration_errors(self) -> None:
        """Return 409, 413, and 422 for invalid registrations."""
        self._register("model", b"one", version="1")

        duplicate = self._register("MODEL", b"two", version="1")
        oversized = self._register("large", b"a" * 17)
        malformed = self._register("invalid", b"one", metadata="[]")
        missing_artifact = self.client.post("/models/model/versions")

        self.assertEqual(duplicate.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(oversized.status_code, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(oversized.json()["limit"], 16)
        self.assertEqual(malformed.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(missing_artifact.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_returns_not_found_without_changing_active_version(self) -> None:
        """Return 404 for missing records and preserve existing activation."""
        self._register("model", b"one", version="1")
        self.client.post("/models/model/versions/1/activate")

        missing_version = self.client.get("/models/model/versions/2")
        missing_history = self.client.get("/models/unknown/versions")
        missing_activation = self.client.post("/models/model/versions/2/activate")

        self.assertEqual(missing_version.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(missing_history.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(missing_activation.status_code, HTTPStatus.NOT_FOUND)
        active = self.client.get("/models/model/versions/1").json()
        self.assertEqual(active["status"], "active")

    def _register(
        self,
        model_name: str,
        artifact: bytes,
        version: str | None = None,
        description: str | None = None,
        metadata: str | None = None,
    ):
        """Submit one multipart model registration request."""
        data = {
            key: value
            for key, value in {
                "version": version,
                "description": description,
                "metadata": metadata,
            }.items()
            if value is not None
        }
        return self.client.post(
            f"/models/{model_name}/versions",
            files={"artifact": ("model.bin", artifact, "application/octet-stream")},
            data=data,
        )
