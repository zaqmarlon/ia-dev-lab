"""Tests for the structured extraction endpoint."""

from http import HTTPStatus
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from src.app import AppHandler


VALID_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
}


class FakeExtractor:
    """Provide deterministic extraction results for endpoint tests."""

    def __init__(self, results: list[object]) -> None:
        """Initialize the fake with results or exceptions to emit."""
        self.results = list(results)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def extract(self, text: str, schema: dict[str, object]) -> dict[str, object]:
        """Record one call and return or raise its configured result."""
        self.calls.append((text, schema))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        if not isinstance(result, dict):
            raise TypeError("Fake result must be an object")
        return result


class TestEntitiesEndpoint(unittest.TestCase):
    """Exercise the HTTP contract of the extraction endpoint."""

    def test_returns_ordered_results_for_multiple_texts(self) -> None:
        """Return one extracted object for each input in matching order."""
        extractor = FakeExtractor([{"name": "Ada"}, {"name": "Linus"}])
        handler = self._build_handler(
            {"texts": ["First", "Second"], "schema": VALID_SCHEMA}, extractor
        )

        AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.OK)
        self.assertEqual(self._response(handler), {"results": [{"name": "Ada"}, {"name": "Linus"}]})
        self.assertEqual([call[0] for call in extractor.calls], ["First", "Second"])

    def test_returns_one_result_for_one_text(self) -> None:
        """Return a single-item results array for one submitted text."""
        handler = self._build_handler(
            {"texts": ["Only"], "schema": VALID_SCHEMA}, FakeExtractor([{"name": "Ada"}])
        )

        AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.OK)
        self.assertEqual(self._response(handler), {"results": [{"name": "Ada"}]})

    def test_returns_bad_request_for_malformed_json(self) -> None:
        """Reject a body that cannot be decoded as JSON."""
        handler = self._build_raw_handler(b"{not-json", FakeExtractor([]))

        AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(self._response(handler), {"detail": "Invalid JSON body"})

    def test_returns_unprocessable_entity_for_invalid_fields(self) -> None:
        """Reject missing, empty, and incorrectly typed request values."""
        payloads = [
            {"schema": VALID_SCHEMA},
            {"texts": [], "schema": VALID_SCHEMA},
            {"texts": [""], "schema": VALID_SCHEMA},
            {"texts": [1], "schema": VALID_SCHEMA},
            {"texts": ["Text"]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                extractor = FakeExtractor([])
                handler = self._build_handler(payload, extractor)

                AppHandler.do_POST(handler)

                self.assertEqual(handler.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
                self.assertEqual(extractor.calls, [])

    def test_rejects_unsupported_schema_before_extraction(self) -> None:
        """Reject unsupported schema keywords without invoking the provider."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1}},
            "required": ["name"],
            "additionalProperties": False,
        }
        extractor = FakeExtractor([])
        handler = self._build_handler({"texts": ["Text"], "schema": schema}, extractor)

        AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(extractor.calls, [])

    def test_returns_bad_gateway_without_partial_results(self) -> None:
        """Discard successful items when a later provider call fails."""
        secret = "private customer record"
        extractor = FakeExtractor([{"name": "Ada"}, RuntimeError(secret)])
        handler = self._build_handler(
            {"texts": ["First", secret], "schema": VALID_SCHEMA}, extractor
        )

        AppHandler.do_POST(handler)

        response = self._response(handler)
        self.assertEqual(handler.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(response, {"detail": "Extraction service failed"})
        self.assertNotIn(secret, json.dumps(response))
        self.assertNotIn("results", response)

    def test_returns_bad_gateway_for_nonconforming_output(self) -> None:
        """Reject provider output that does not satisfy the schema."""
        handler = self._build_handler(
            {"texts": ["Text"], "schema": VALID_SCHEMA}, FakeExtractor([{"other": "value"}])
        )

        AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertNotIn("results", self._response(handler))

    def test_returns_bad_gateway_when_provider_cannot_initialize(self) -> None:
        """Translate provider configuration failures into a safe response."""
        handler = self._build_handler(
            {"texts": ["Text"], "schema": VALID_SCHEMA}, FakeExtractor([])
        )
        handler.extractor = None

        with patch("src.app.OpenAIStructuredExtractor", side_effect=RuntimeError("secret")):
            AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(self._response(handler), {"detail": "Extraction service failed"})

    def test_rejects_legacy_text_payload(self) -> None:
        """Reject the replaced singular text request contract."""
        handler = self._build_handler(
            {"text": "Legacy", "schema": VALID_SCHEMA}, FakeExtractor([])
        )

        AppHandler.do_POST(handler)

        self.assertEqual(handler.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def _build_handler(
        self, payload: object, extractor: FakeExtractor
    ) -> AppHandler:
        """Create a handler containing an encoded JSON request."""
        return self._build_raw_handler(json.dumps(payload).encode("utf-8"), extractor)

    def _build_raw_handler(self, body: bytes, extractor: FakeExtractor) -> AppHandler:
        """Create a handler wired with in-memory request and response streams."""
        handler = AppHandler.__new__(AppHandler)
        handler.path = "/entities"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        handler.status_code = None
        handler.extractor = extractor
        handler.send_response = self._send_response.__get__(handler, AppHandler)
        handler.send_header = self._send_header.__get__(handler, AppHandler)
        handler.end_headers = self._end_headers.__get__(handler, AppHandler)
        return handler

    def _response(self, handler: AppHandler) -> dict[str, object]:
        """Decode the captured JSON response."""
        handler.wfile.seek(0)
        return json.loads(handler.wfile.read().decode("utf-8"))

    def _send_response(self, status_code: int) -> None:
        """Capture the response status code."""
        self.status_code = status_code

    def _send_header(self, name: str, value: str) -> None:
        """Ignore response headers in the test harness."""
        return None

    def _end_headers(self) -> None:
        """Ignore end-of-headers in the test harness."""
        return None
