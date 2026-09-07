"""Structured extraction service and OpenAI provider adapter."""

from collections.abc import Sequence
import json
import os
from typing import Any, Protocol

from jsonschema import validate
from openai import OpenAI

from src.schemas import ExtractionError, ExtractionResponse, JsonObject


class StructuredExtractor(Protocol):
    """Define the provider boundary for extracting one structured object."""

    def extract(self, text: str, schema: JsonObject) -> JsonObject:
        """Extract an object from text according to the supplied schema."""
        ...


class OpenAIStructuredExtractor:
    """Extract structured objects through the OpenAI Responses API."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        """Initialize the adapter with an optional client and model override."""
        self._client = client or OpenAI()
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")

    def extract(self, text: str, schema: JsonObject) -> JsonObject:
        """Request and decode one schema-constrained extraction."""
        response = self._client.responses.create(
            model=self._model,
            instructions="Extract only information supported by the supplied source text.",
            input=text,
            reasoning={"effort": "medium"},
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "text_extraction",
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        result = json.loads(response.output_text)
        if not isinstance(result, dict):
            raise ValueError("Provider output must be an object")
        return result


def extract_texts(
    texts: Sequence[str], schema: JsonObject, extractor: StructuredExtractor
) -> ExtractionResponse:
    """Extract and validate ordered results, failing the batch atomically."""
    results: list[JsonObject] = []
    for text in texts:
        try:
            result = extractor.extract(text, schema)
            validate(instance=result, schema=schema)
        except Exception:
            raise ExtractionError("Extraction service failed") from None
        results.append(result)
    return ExtractionResponse(tuple(results))
