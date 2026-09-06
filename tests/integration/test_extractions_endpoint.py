"""HTTP integration tests for schema-driven batch extraction."""

from pathlib import Path
import tempfile
import unittest

from src.app import create_app
from src.inference import StubInferenceProvider
from src.settings import Settings
from tests.http_client import ASGITestClient


class RecordingInferenceProvider(StubInferenceProvider):
    """Record every source accepted by the HTTP extraction pipeline."""

    def __init__(self) -> None:
        """Initialize an empty invocation record."""
        super().__init__()
        self.source_ids: list[str] = []

    def infer(self, source_id: str, text: str, property_names: tuple[str, ...]) -> object:
        """Record the source before returning deterministic stub values."""
        self.source_ids.append(source_id)
        return super().infer(source_id, text, property_names)


class TestExtractionsEndpoint(unittest.TestCase):
    """Verify valid, duplicate-content, absent-value, and partial-failure journeys."""

    def setUp(self) -> None:
        """Create an isolated default application."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name)
        self.settings = Settings(self.data_dir, self.data_dir / "catalog.sqlite3")
        self.client = ASGITestClient(create_app(self.settings))

    def tearDown(self) -> None:
        """Remove isolated application data."""
        self.client.close()
        self.temporary_directory.cleanup()

    def payload(self, *source_ids: str) -> dict[str, object]:
        """Build a valid batch whose sources intentionally share content."""
        return {
            "texts": [{"id": source_id, "text": "Identical input"} for source_id in source_ids],
            "schema": {"properties": [
                {"name": "organization", "type": "string", "required": True},
                {"name": "location", "type": "string"},
            ]},
        }

    def test_single_and_duplicate_content_batches_return_explicit_stub_states(self) -> None:
        """Verify valid sources retain identity and never receive fabricated values."""
        single = self.client.post("/extractions", json=self.payload("only"))
        multiple = self.client.post("/extractions", json=self.payload("first", "second"))
        self.assertEqual((single.status_code, multiple.status_code), (200, 200))
        self.assertEqual(single.json()["execution_mode"], "stub")
        self.assertEqual(
            [item["source_id"] for item in multiple.json()["outcomes"]],
            ["first", "second"],
        )
        for outcome in multiple.json()["outcomes"]:
            for property_result in outcome["properties"].values():
                self.assertIsNone(property_result["value"])
                self.assertEqual(property_result["inference_status"], "not_inferred")
                self.assertEqual(
                    property_result["uncertainty"],
                    {"value": None, "status": "not_calculated"},
                )

    def test_provider_failure_returns_one_failed_outcome_in_original_order(self) -> None:
        """Verify an accepted item failure does not fail the HTTP request."""
        client = ASGITestClient(
            create_app(self.settings, inference_provider=StubInferenceProvider(("second",)))
        )
        response = client.post("/extractions", json=self.payload("first", "second", "third"))
        client.close()
        self.assertEqual(response.status_code, 200)
        outcomes = response.json()["outcomes"]
        self.assertEqual([item["source_id"] for item in outcomes], ["first", "second", "third"])
        self.assertEqual([item["status"] for item in outcomes], [
            "completed", "failed", "completed",
        ])
        self.assertEqual(outcomes[1]["properties"], {})
        self.assertEqual(outcomes[1]["error"]["code"], "processing_failed")

    def test_invalid_requests_are_actionable_and_never_invoke_inference(self) -> None:
        """Verify structural and configured limits reject the whole batch first."""
        provider = RecordingInferenceProvider()
        client = ASGITestClient(create_app(self.settings, inference_provider=provider))
        requests = (
            {"texts": [], "schema": {"properties": [{"name": "value", "type": "string"}]}},
            self.payload("duplicate", "duplicate"),
            {"texts": [{"id": "blank", "text": " "}], "schema": {
                "properties": [{"name": "value", "type": "string"}],
            }},
            {"texts": [{"id": "source", "text": "content"}], "schema": {"properties": []}},
            {"texts": [{"id": "source", "text": "x" * 100_001}], "schema": {
                "properties": [{"name": "value", "type": "string"}],
            }},
        )
        statuses = [client.post("/extractions", json=request).status_code for request in requests]
        client.close()
        self.assertEqual(statuses, [422, 422, 422, 422, 413])
        self.assertEqual(provider.source_ids, [])

    def test_configured_text_count_limit_returns_422_with_limit(self) -> None:
        """Verify application settings control the accepted batch count."""
        settings = Settings(
            self.data_dir,
            self.data_dir / "count-limit.sqlite3",
            max_extraction_texts=1,
        )
        provider = RecordingInferenceProvider()
        client = ASGITestClient(create_app(settings, inference_provider=provider))
        response = client.post("/extractions", json=self.payload("first", "second"))
        client.close()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["limit"], 1)
        self.assertEqual(provider.source_ids, [])


if __name__ == "__main__":
    unittest.main()
