"""Unit tests for schema-driven extraction orchestration."""

import unittest

from src.extraction import StubModelCatalog
from src.inference import StubInferenceProvider
from src.schemas import ExtractionRequest
from src.service import ExtractionService
from src.uncertainty import StubUncertaintyEstimator


def request_with_sources(*source_ids: str) -> ExtractionRequest:
    """Build an extraction request with duplicate content and two properties."""
    return ExtractionRequest.model_validate(
        {
            "texts": [{"id": source_id, "text": "Same content"} for source_id in source_ids],
            "schema": {
                "properties": [
                    {"name": "organization", "type": "string", "required": True},
                    {"name": "location", "type": "string"},
                ]
            },
        }
    )


class TestExtractionService(unittest.TestCase):
    """Verify ordered extraction and isolated item failures."""

    def create_service(self, failing_source_ids: tuple[str, ...] = ()) -> ExtractionService:
        """Create a service with deterministic replaceable stubs."""
        return ExtractionService(
            StubInferenceProvider(failing_source_ids),
            StubUncertaintyEstimator(),
            StubModelCatalog(),
            max_texts=10,
            max_characters=100_000,
        )

    def test_batch_preserves_identity_order_and_requested_properties(self) -> None:
        """Verify duplicate content produces distinct ordered outcomes."""
        result = self.create_service().extract(request_with_sources("first", "second"))
        self.assertEqual(result.execution_mode.value, "stub")
        self.assertEqual([item.source_id for item in result.outcomes], ["first", "second"])
        for outcome in result.outcomes:
            self.assertEqual(outcome.status.value, "completed")
            self.assertEqual(set(outcome.properties), {"organization", "location"})
            for property_result in outcome.properties.values():
                self.assertIsNone(property_result.value)
                self.assertEqual(property_result.inference_status.value, "not_inferred")
                self.assertIsNone(property_result.uncertainty.value)
                self.assertEqual(property_result.uncertainty.status.value, "not_calculated")

    def test_failure_is_isolated_to_configured_source(self) -> None:
        """Verify one provider error does not discard other outcomes."""
        result = self.create_service(("second",)).extract(
            request_with_sources("first", "second", "third")
        )
        self.assertEqual([item.status.value for item in result.outcomes], [
            "completed", "failed", "completed",
        ])
        self.assertEqual(result.outcomes[1].properties, {})
        self.assertEqual(result.outcomes[1].error.code, "processing_failed")


if __name__ == "__main__":
    unittest.main()
