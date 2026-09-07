"""Tests for the ping endpoint."""

from http import HTTPStatus
import unittest

from src.app import create_app
from tests.http_client import HttpClient


class TestPingEndpoint(unittest.TestCase):
    """Exercise the service availability endpoint."""

    def test_ping_endpoint_returns_pong(self) -> None:
        """Return the pong payload."""
        response = HttpClient(create_app()).get("/ping")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), {"message": "pong"})
