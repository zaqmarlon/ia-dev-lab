"""Tests for the structured extraction endpoint."""

from http import HTTPStatus
import json
import unittest
from unittest.mock import patch

from src.app import create_app
from tests.http_client import HttpClient


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
        response = self._client(extractor).post(
            "/entities", json={"texts": ["First", "Second"], "schema": VALID_SCHEMA}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), {"results": [{"name": "Ada"}, {"name": "Linus"}]})
        self.assertEqual([call[0] for call in extractor.calls], ["First", "Second"])

    def test_returns_one_result_for_one_text(self) -> None:
        """Return a single-item results array for one submitted text."""
        response = self._client(FakeExtractor([{"name": "Ada"}])).post(
            "/entities", json={"texts": ["Only"], "schema": VALID_SCHEMA}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), {"results": [{"name": "Ada"}]})

    def test_returns_bad_request_for_malformed_json(self) -> None:
        """Reject a body that cannot be decoded as JSON."""
        response = self._client(FakeExtractor([])).post(
            "/entities", content=b"{not-json", headers={"Content-Type": "application/json"}
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.json(), {"detail": "Invalid JSON body"})

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
                response = self._client(extractor).post("/entities", json=payload)

                self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
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
        response = self._client(extractor).post(
            "/entities", json={"texts": ["Text"], "schema": schema}
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(extractor.calls, [])

    def test_returns_bad_gateway_without_partial_results(self) -> None:
        """Discard successful items when a later provider call fails."""
        secret = "private customer record"
        response = self._client(
            FakeExtractor([{"name": "Ada"}, RuntimeError(secret)])
        ).post(
            "/entities", json={"texts": ["First", secret], "schema": VALID_SCHEMA}
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(response.json(), {"detail": "Extraction service failed"})
        self.assertNotIn(secret, json.dumps(response.json()))

    def test_returns_bad_gateway_for_nonconforming_output(self) -> None:
        """Reject provider output that does not satisfy the schema."""
        response = self._client(FakeExtractor([{"other": "value"}])).post(
            "/entities", json={"texts": ["Text"], "schema": VALID_SCHEMA}
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertNotIn("results", response.json())

    def test_returns_bad_gateway_when_provider_cannot_initialize(self) -> None:
        """Translate provider configuration failures into a safe response."""
        with patch("src.app.OpenAIStructuredExtractor", side_effect=RuntimeError("secret")):
            response = HttpClient(create_app()).post(
                "/entities", json={"texts": ["Text"], "schema": VALID_SCHEMA}
            )

        self.assertEqual(response.status_code, HTTPStatus.BAD_GATEWAY)
        self.assertEqual(response.json(), {"detail": "Extraction service failed"})

    def test_rejects_legacy_text_payload(self) -> None:
        """Reject the replaced singular text request contract."""
        response = self._client(FakeExtractor([])).post(
            "/entities", json={"text": "Legacy", "schema": VALID_SCHEMA}
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def _client(self, extractor: FakeExtractor) -> HttpClient:
        """Create a test client with a deterministic extractor."""
        return HttpClient(create_app(extractor))
