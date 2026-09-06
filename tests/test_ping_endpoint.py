"""Tests for the ping endpoint."""

from pathlib import Path
import tempfile
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import ASGITestClient


class TestPingEndpoint(unittest.TestCase):
    """Verify the existing availability endpoint."""

    def test_ping_endpoint_returns_pong(self) -> None:
        """Verify the endpoint returns the pong payload."""
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            client = ASGITestClient(
                create_app(Settings(data_dir, data_dir / "catalog.sqlite3"))
            )
            response = client.get("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "pong"})


if __name__ == "__main__":
    unittest.main()
