"""Tests for the ping endpoint."""

from http import HTTPStatus
from io import BytesIO
import json
import unittest

from src.app import AppHandler


class TestPingEndpoint(unittest.TestCase):
    """Integration-style tests for the ping endpoint handler."""

    def test_ping_endpoint_returns_pong(self) -> None:
        """Verify the endpoint returns the pong payload."""
        handler = self._build_handler()

        AppHandler.do_GET(handler)

        handler.wfile.seek(0)
        response = json.loads(handler.wfile.read().decode("utf-8"))

        self.assertEqual(handler.status_code, HTTPStatus.OK)
        self.assertEqual(response, {"message": "pong"})

    def _build_handler(self) -> AppHandler:
        """Create a handler instance wired with an in-memory response stream."""
        handler = AppHandler.__new__(AppHandler)
        handler.path = "/ping"
        handler.wfile = BytesIO()
        handler.status_code = None
        handler.send_response = self._send_response.__get__(handler, AppHandler)
        handler.send_header = self._send_header.__get__(handler, AppHandler)
        handler.end_headers = self._end_headers.__get__(handler, AppHandler)
        return handler

    def _send_response(self, status_code: int) -> None:
        """Capture the response status code."""
        self.status_code = status_code

    def _send_header(self, name: str, value: str) -> None:
        """Ignore response headers in the test harness."""
        return None

    def _end_headers(self) -> None:
        """Ignore end-of-headers in the test harness."""
        return None
