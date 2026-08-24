"""HTTP application exposing the entity extraction endpoint."""

from http.server import BaseHTTPRequestHandler
import json

from src.service import get_mocked_entities


class AppHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for the application."""

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path != "/entities":
            self._send_json(404, {"detail": "Not Found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length) or b"{}")
        text = payload.get("text", "")
        entities = get_mocked_entities(text)
        self._send_json(200, {"entities": entities})

    def _send_json(self, status_code: int, body: dict) -> None:
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
