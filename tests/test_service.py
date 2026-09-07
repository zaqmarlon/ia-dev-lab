"""Tests for the structured extraction service and provider adapter."""

from types import SimpleNamespace
import unittest

from src.schemas import ExtractionError
from src.service import OpenAIStructuredExtractor, extract_texts


VALID_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
}


class FakeExtractor:
    """Return configured values without calling an external provider."""

    def __init__(self, results: list[object]) -> None:
        """Initialize the fake result queue."""
        self.results = list(results)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def extract(self, text: str, schema: dict[str, object]) -> dict[str, object]:
        """Record an extraction and return its configured value."""
        self.calls.append((text, schema))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        if not isinstance(result, dict):
            raise TypeError("Fake result must be an object")
        return result


class FakeResponses:
    """Capture Responses API arguments and return encoded output."""

    def __init__(self, output_text: str) -> None:
        """Initialize the fake response text."""
        self.output_text = output_text
        self.arguments: dict[str, object] | None = None

    def create(self, **arguments: object) -> SimpleNamespace:
        """Capture request arguments and return a response object."""
        self.arguments = arguments
        return SimpleNamespace(output_text=self.output_text)


class TestExtractionService(unittest.TestCase):
    """Verify ordered, validated, and atomic service behavior."""

    def test_extracts_each_text_in_order_with_same_schema(self) -> None:
        """Preserve input ordering across independent provider calls."""
        extractor = FakeExtractor([{"name": "Ada"}, {"name": "Linus"}])

        response = extract_texts(["First", "Second"], VALID_SCHEMA, extractor)

        self.assertEqual(response.to_dict(), {"results": [{"name": "Ada"}, {"name": "Linus"}]})
        self.assertEqual(extractor.calls, [("First", VALID_SCHEMA), ("Second", VALID_SCHEMA)])

    def test_fails_fast_without_exposing_provider_details(self) -> None:
        """Stop at the first failure and replace sensitive provider errors."""
        secret = "private customer record"
        extractor = FakeExtractor([{"name": "Ada"}, RuntimeError(secret), {"name": "Ignored"}])

        with self.assertRaises(ExtractionError) as raised:
            extract_texts(["First", secret, "Third"], VALID_SCHEMA, extractor)

        self.assertEqual(str(raised.exception), "Extraction service failed")
        self.assertIsNone(raised.exception.__cause__)
        self.assertNotIn(secret, str(raised.exception))
        self.assertEqual(len(extractor.calls), 2)

    def test_rejects_output_that_does_not_match_schema(self) -> None:
        """Reject a provider object that fails local schema validation."""
        extractor = FakeExtractor([{"name": 42}])

        with self.assertRaises(ExtractionError):
            extract_texts(["Text"], VALID_SCHEMA, extractor)


class TestOpenAIStructuredExtractor(unittest.TestCase):
    """Verify construction of a structured Responses API request."""

    def test_requests_non_stored_strict_json_schema_output(self) -> None:
        """Send the source and schema through the current structured-output fields."""
        responses = FakeResponses('{"name": "Ada"}')
        client = SimpleNamespace(responses=responses)
        extractor = OpenAIStructuredExtractor(client=client, model="test-model")

        result = extractor.extract("Ada wrote software.", VALID_SCHEMA)

        self.assertEqual(result, {"name": "Ada"})
        self.assertIsNotNone(responses.arguments)
        self.assertEqual(responses.arguments["model"], "test-model")
        self.assertEqual(responses.arguments["input"], "Ada wrote software.")
        self.assertFalse(responses.arguments["store"])
        self.assertEqual(responses.arguments["text"]["format"]["schema"], VALID_SCHEMA)
        self.assertTrue(responses.arguments["text"]["format"]["strict"])
