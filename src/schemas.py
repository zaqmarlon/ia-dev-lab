"""Data structures and validation for structured text extraction."""

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, SchemaError


JsonObject = dict[str, Any]


class RequestValidationError(ValueError):
    """Represent an invalid extraction request payload."""


class SchemaValidationError(ValueError):
    """Represent an invalid or unsupported extraction schema."""


class ExtractionError(RuntimeError):
    """Represent a safe client-facing extraction failure."""


@dataclass(frozen=True)
class ExtractionRequest:
    """Contain validated texts and their shared extraction schema."""

    texts: tuple[str, ...]
    schema: JsonObject


@dataclass(frozen=True)
class ExtractionResponse:
    """Contain ordered objects extracted from the submitted texts."""

    results: tuple[JsonObject, ...]

    def to_dict(self) -> JsonObject:
        """Return the HTTP response representation."""
        return {"results": list(self.results)}


SUPPORTED_KEYWORDS = {
    "additionalProperties",
    "anyOf",
    "description",
    "enum",
    "items",
    "properties",
    "required",
    "title",
    "type",
}
SUPPORTED_TYPES = {"array", "boolean", "integer", "null", "number", "object", "string"}


def parse_extraction_request(payload: object) -> ExtractionRequest:
    """Validate and convert an HTTP payload into an extraction request."""
    if not isinstance(payload, dict):
        raise RequestValidationError("Request body must be a JSON object")

    texts = payload.get("texts")
    if not isinstance(texts, list) or not texts:
        raise RequestValidationError("texts must be a non-empty array")
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise RequestValidationError("texts must contain only non-empty strings")

    schema = payload.get("schema")
    if not isinstance(schema, dict):
        raise RequestValidationError("schema must be a JSON object")

    validate_extraction_schema(schema)
    return ExtractionRequest(tuple(texts), dict(schema))


def validate_extraction_schema(schema: JsonObject) -> None:
    """Validate JSON Schema syntax and the supported structured-output subset."""
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise SchemaValidationError("schema is not valid JSON Schema") from error

    if schema.get("type") != "object":
        raise SchemaValidationError("schema root type must be object")
    _validate_supported_schema_node(schema, "schema")


def _validate_supported_schema_node(schema: JsonObject, path: str) -> None:
    """Validate one schema node and its nested object or array schemas."""
    if set(schema) - SUPPORTED_KEYWORDS:
        raise SchemaValidationError(f"{path} contains unsupported keywords")

    schema_types = _schema_types(schema.get("type"), path)
    if "object" in schema_types:
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, dict):
            raise SchemaValidationError(f"{path}.properties must be an object")
        if schema.get("additionalProperties") is not False:
            raise SchemaValidationError(f"{path}.additionalProperties must be false")
        if not isinstance(required, list) or set(required) != set(properties):
            raise SchemaValidationError(f"{path}.required must include every property")
        for name, child in properties.items():
            if not isinstance(child, dict):
                raise SchemaValidationError(f"{path}.properties.{name} must be an object")
            _validate_supported_schema_node(child, f"{path}.properties.{name}")

    if "array" in schema_types:
        items = schema.get("items")
        if not isinstance(items, dict):
            raise SchemaValidationError(f"{path}.items must be an object")
        _validate_supported_schema_node(items, f"{path}.items")

    any_of = schema.get("anyOf")
    if any_of is not None:
        if not isinstance(any_of, list) or not any_of:
            raise SchemaValidationError(f"{path}.anyOf must be a non-empty array")
        for index, child in enumerate(any_of):
            if not isinstance(child, dict):
                raise SchemaValidationError(f"{path}.anyOf[{index}] must be an object")
            _validate_supported_schema_node(child, f"{path}.anyOf[{index}]")


def _schema_types(value: object, path: str) -> set[str]:
    """Normalize and validate a schema type declaration."""
    if isinstance(value, str):
        values = {value}
    elif isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        values = set(value)
    else:
        raise SchemaValidationError(f"{path}.type must declare a supported type")
    if not values <= SUPPORTED_TYPES:
        raise SchemaValidationError(f"{path}.type contains an unsupported type")
    return values
