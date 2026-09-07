"""End-to-end persistence test for the model registry."""

from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import HttpClient


class TestModelRegistryEndToEnd(unittest.TestCase):
    """Exercise model lifecycle persistence across application instances."""

    def test_recovers_history_and_active_version_after_recreation(self) -> None:
        """Preserve registered versions and lifecycle state after restart."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(root, root / "catalog.sqlite3", 1024)
            first_client = HttpClient(create_app(settings=settings))

            for artifact in (b"version-one", b"version-two"):
                response = first_client.post(
                    "/models/extractor/versions",
                    files={
                        "artifact": (
                            "model.bin",
                            artifact,
                            "application/octet-stream",
                        )
                    },
                )
                self.assertEqual(response.status_code, HTTPStatus.CREATED)
            activation = first_client.post(
                "/models/extractor/versions/2/activate"
            )
            self.assertEqual(activation.status_code, HTTPStatus.OK)
            first_client.close()

            recreated_client = HttpClient(create_app(settings=settings))
            history = recreated_client.get("/models/extractor/versions")
            recreated_client.close()

        self.assertEqual(history.status_code, HTTPStatus.OK)
        self.assertEqual(
            [(item["version"], item["status"]) for item in history.json()["versions"]],
            [(2, "active"), (1, "registered")],
        )
