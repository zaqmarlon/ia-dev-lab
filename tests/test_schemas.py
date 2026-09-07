"""Tests for extraction request and schema validation."""

import unittest

from src.schemas import (
    RequestValidationError,
    SchemaValidationError,
    parse_extraction_request,
    validate_extraction_schema,
)


VALID_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
}


class TestExtractionRequest(unittest.TestCase):
    """Verify conversion of external request values into typed data."""

    def test_parses_valid_request(self) -> None:
        """Create an immutable request from valid values."""
        request = parse_extraction_request({"texts": ["One", "Two"], "schema": VALID_SCHEMA})

        self.assertEqual(request.texts, ("One", "Two"))
        self.assertEqual(request.schema, VALID_SCHEMA)

    def test_rejects_non_object_body(self) -> None:
        """Reject a JSON body that is not an object."""
        with self.assertRaises(RequestValidationError):
            parse_extraction_request(["Text"])

    def test_rejects_invalid_text_collections(self) -> None:
        """Reject absent, empty, or incorrectly typed text values."""
        invalid_values = [None, "Text", [], [""], ["   "], [1], ["Text", None]]
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(RequestValidationError):
                parse_extraction_request({"texts": value, "schema": VALID_SCHEMA})


class TestExtractionSchema(unittest.TestCase):
    """Verify syntax and provider-subset schema validation."""

    def test_accepts_nested_supported_schema(self) -> None:
        """Accept nested objects, arrays, enums, and nullable types."""
        schema = {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": ["integer", "null"]},
                    },
                    "required": ["name", "age"],
                    "additionalProperties": False,
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["person", "tags"],
            "additionalProperties": False,
        }

        validate_extraction_schema(schema)

    def test_rejects_invalid_json_schema(self) -> None:
        """Reject a schema that violates JSON Schema syntax."""
        schema = {"type": 7}

        with self.assertRaises(SchemaValidationError):
            validate_extraction_schema(schema)

    def test_rejects_non_object_root(self) -> None:
        """Reject a schema whose root is not an object."""
        with self.assertRaises(SchemaValidationError):
            validate_extraction_schema({"type": "string"})

    def test_rejects_unsupported_keyword(self) -> None:
        """Reject schema features outside the provider-supported subset."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string", "pattern": "^[A-Z]"}},
            "required": ["name"],
            "additionalProperties": False,
        }

        with self.assertRaises(SchemaValidationError):
            validate_extraction_schema(schema)

    def test_requires_all_properties_and_disallows_additional_values(self) -> None:
        """Enforce strict structured-output object requirements."""
        for required, additional in [([], False), (["name"], True)]:
            schema = {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": required,
                "additionalProperties": additional,
            }
            with self.subTest(schema=schema), self.assertRaises(SchemaValidationError):
                validate_extraction_schema(schema)
