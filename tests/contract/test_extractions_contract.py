"""Contract tests for the schema-driven extraction endpoint."""

from pathlib import Path
import tempfile
import unittest

from src.app import create_app
from src.settings import Settings
from tests.http_client import ASGITestClient


class TestExtractionsContract(unittest.TestCase):
    """Verify the published extraction path and successful response shape."""

    def setUp(self) -> None:
        """Create an isolated application for each contract test."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_dir = Path(self.temporary_directory.name)
        self.client = ASGITestClient(create_app(Settings(data_dir, data_dir / "catalog.sqlite3")))

    def tearDown(self) -> None:
        """Remove isolated application data."""
        self.client.close()
        self.temporary_directory.cleanup()

    def valid_payload(self) -> dict[str, object]:
        """Return a minimal request matching the published contract."""
        return {
            "texts": [{"id": "document-1", "text": "OpenAI is in San Francisco."}],
            "schema": {"properties": [
                {"name": "organization", "type": "string"},
                {"name": "location", "type": "string"},
            ]},
        }

    def test_openapi_publishes_extraction_operation_and_responses(self) -> None:
        """Verify POST and every contracted response status are published."""
        operation = self.client.get("/openapi.json").json()["paths"]["/extractions"]["post"]
        self.assertEqual(set(operation["responses"]), {"200", "413", "422"})

    def test_success_response_matches_required_contract_shape(self) -> None:
        """Verify a successful response exposes stable batch and property fields."""
        response = self.client.post("/extractions", json=self.valid_payload())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"execution_mode", "model", "outcomes"})
        self.assertEqual(set(body["model"]), {"name", "version"})
        self.assertEqual(len(body["outcomes"]), 1)
        outcome = body["outcomes"][0]
        self.assertEqual(set(outcome), {"source_id", "status", "properties", "error"})
        self.assertEqual(set(outcome["properties"]), {"organization", "location"})
        for property_result in outcome["properties"].values():
            self.assertEqual(set(property_result), {"value", "inference_status", "uncertainty"})
            self.assertEqual(set(property_result["uncertainty"]), {"value", "status"})

    def test_structural_validation_uses_actionable_422_contract(self) -> None:
        """Verify malformed requests use the standard error response."""
        response = self.client.post("/extractions", json={"texts": [], "schema": {"properties": []}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(set(response.json()), {"detail", "limit"})
        self.assertTrue(response.json()["detail"])

    def test_excessive_volume_uses_413_contract_and_discloses_limit(self) -> None:
        """Verify oversized content returns the configured character limit."""
        request = self.valid_payload()
        request["texts"][0]["text"] = "x" * 100_001
        response = self.client.post("/extractions", json=request)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["limit"], 100_000)
        self.assertIn("100000", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
