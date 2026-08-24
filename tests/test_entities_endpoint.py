"""Tests for the entity extraction endpoint."""

from http import HTTPStatus
from io import BytesIO
import json
import unittest

from src.app import AppHandler


class TestEntitiesEndpoint(unittest.TestCase):
    """Integration-style tests for the entities endpoint handler."""

    def test_entities_endpoint_returns_mocked_response(self) -> None:
        """Verify the endpoint returns the mocked entity payload."""
        handler = self._build_handler({"text": "Any input text"})

        AppHandler.do_POST(handler)

        handler.wfile.seek(0)
        response = json.loads(handler.wfile.read().decode("utf-8"))

        self.assertEqual(handler.status_code, HTTPStatus.OK)
        self.assertEqual(
            response,
            {
                "entities": [
                    {"text": "OpenAI", "label": "ORG", "confidence": 0.98},
                    {"text": "San Francisco", "label": "GPE", "confidence": 0.95},
                ]
            },
        )

    def _build_handler(self, payload: dict[str, str]) -> AppHandler:
        """Create a handler instance wired with in-memory request and response streams."""
        handler = AppHandler.__new__(AppHandler)
        body = json.dumps(payload).encode("utf-8")
        handler.path = "/entities"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = BytesIO(body)
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
