"""Unit tests for extraction request validation and configured limits."""

import unittest

from pydantic import ValidationError

from src.extraction import ExtractionRequestError, ExtractionVolumeError, StubModelCatalog
from src.inference import StubInferenceProvider
from src.schemas import ExtractionRequest
from src.service import ExtractionService
from src.uncertainty import StubUncertaintyEstimator


class RecordingInferenceProvider(StubInferenceProvider):
    """Record source identifiers received by the deterministic provider."""

    def __init__(self) -> None:
        """Initialize an empty invocation record."""
        super().__init__()
        self.source_ids: list[str] = []

    def infer(self, source_id: str, text: str, property_names: tuple[str, ...]) -> object:
        """Record the invocation before returning stub results."""
        self.source_ids.append(source_id)
        return super().infer(source_id, text, property_names)


def payload(texts: list[dict[str, str]], properties: list[dict[str, object]]) -> dict[str, object]:
    """Build a raw extraction payload for validation tests."""
    return {"texts": texts, "schema": {"properties": properties}}


class TestRequestValidation(unittest.TestCase):
    """Verify structural validation and exact configurable boundaries."""

    def test_rejects_empty_or_blank_source_fields(self) -> None:
        """Verify at least one source with non-blank identity and text is required."""
        valid_properties = [{"name": "value", "type": "string"}]
        invalid_texts = (
            [],
            [{"id": " ", "text": "content"}],
            [{"id": "source", "text": " \t "}],
        )
        for texts in invalid_texts:
            with self.subTest(texts=texts), self.assertRaises(ValidationError):
                ExtractionRequest.model_validate(payload(texts, valid_properties))

    def test_rejects_duplicate_source_identifiers(self) -> None:
        """Verify source identity is unique even when content duplication is allowed."""
        with self.assertRaisesRegex(ValidationError, "source identifiers must be unique"):
            ExtractionRequest.model_validate(payload(
                [{"id": "same", "text": "one"}, {"id": "same", "text": "two"}],
                [{"name": "value", "type": "string"}],
            ))

    def test_rejects_empty_duplicate_blank_and_unsupported_properties(self) -> None:
        """Verify the extraction schema contains unique supported named properties."""
        valid_texts = [{"id": "source", "text": "content"}]
        invalid_properties = (
            [],
            [{"name": " ", "type": "string"}],
            [{"name": "value", "type": "string"}, {"name": "value", "type": "number"}],
            [{"name": "value", "type": "object"}],
        )
        for properties in invalid_properties:
            with self.subTest(properties=properties), self.assertRaises(ValidationError):
                ExtractionRequest.model_validate(payload(valid_texts, properties))

    def test_text_count_limit_rejects_before_inference(self) -> None:
        """Verify the configured text count is enforced before provider invocation."""
        provider = RecordingInferenceProvider()
        service = ExtractionService(
            provider,
            StubUncertaintyEstimator(),
            StubModelCatalog(),
            max_texts=1,
            max_characters=100_000,
        )
        request = ExtractionRequest.model_validate(payload(
            [{"id": "one", "text": "a"}, {"id": "two", "text": "b"}],
            [{"name": "value", "type": "string"}],
        ))
        with self.assertRaisesRegex(ExtractionRequestError, "configured limit of 1"):
            service.extract(request)
        self.assertEqual(provider.source_ids, [])

    def test_character_limit_accepts_exact_boundary_and_rejects_one_above(self) -> None:
        """Verify character volume uses an inclusive configured maximum."""
        provider = RecordingInferenceProvider()
        service = ExtractionService(
            provider,
            StubUncertaintyEstimator(),
            StubModelCatalog(),
            max_texts=10,
            max_characters=100_000,
        )
        exact = ExtractionRequest.model_validate(payload(
            [{"id": "exact", "text": "x" * 100_000}],
            [{"name": "value", "type": "string"}],
        ))
        above = ExtractionRequest.model_validate(payload(
            [{"id": "above", "text": "x" * 100_001}],
            [{"name": "value", "type": "string"}],
        ))
        self.assertEqual(service.extract(exact).outcomes[0].status.value, "completed")
        with self.assertRaises(ExtractionVolumeError) as raised:
            service.extract(above)
        self.assertEqual(raised.exception.limit, 100_000)
        self.assertEqual(provider.source_ids, ["exact"])


if __name__ == "__main__":
    unittest.main()
