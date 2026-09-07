"""HTTP application exposing health and structured extraction endpoints."""

from http.server import BaseHTTPRequestHandler
import json

from src.schemas import (
    ExtractionError,
    JsonObject,
    RequestValidationError,
    SchemaValidationError,
    parse_extraction_request,
)
from src.service import OpenAIStructuredExtractor, StructuredExtractor, extract_texts


class AppHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the application."""

    extractor: StructuredExtractor | None = None

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path != "/ping":
            self._send_json(404, {"detail": "Not Found"})
            return

        self._send_json(200, {"message": "pong"})

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path != "/entities":
            self._send_json(404, {"detail": "Not Found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                raise ValueError
            payload = json.loads(self.rfile.read(content_length))
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"detail": "Invalid JSON body"})
            return

        try:
            request = parse_extraction_request(payload)
        except (RequestValidationError, SchemaValidationError) as error:
            self._send_json(422, {"detail": str(error)})
            return

        try:
            response = extract_texts(request.texts, request.schema, self._get_extractor())
        except ExtractionError:
            self._send_json(502, {"detail": "Extraction service failed"})
            return

        self._send_json(200, response.to_dict())

    def _get_extractor(self) -> StructuredExtractor:
        """Return the injected extractor or create the production adapter."""
        if self.extractor is None:
            try:
                self.extractor = OpenAIStructuredExtractor()
            except Exception:
                raise ExtractionError("Extraction service failed") from None
        return self.extractor

    def _send_json(self, status_code: int, body: JsonObject) -> None:
        """Send a JSON response."""
        data = json.dumps(body).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_app() -> type[BaseHTTPRequestHandler]:
    """Return the request handler class used by the server."""
    return AppHandler
