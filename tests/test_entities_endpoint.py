"""Tests for the entity extraction endpoint."""

from pathlib import Path
import tempfile
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import ASGITestClient


class TestEntitiesEndpoint(unittest.TestCase):
    """Verify the existing mocked entity extraction endpoint."""

    def test_entities_endpoint_returns_mocked_response(self) -> None:
        """Verify the endpoint returns the mocked entity payload."""
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            client = ASGITestClient(
                create_app(Settings(data_dir, data_dir / "catalog.sqlite3"))
            )
            response = client.post("/entities", json={"text": "Any input text"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "entities": [
                    {"text": "OpenAI", "label": "ORG", "confidence": 0.98},
                    {"text": "San Francisco", "label": "GPE", "confidence": 0.95},
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
