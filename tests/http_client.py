"""Synchronous test facade over HTTPX asynchronous ASGI transport."""

import asyncio
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response


class HttpClient:
    """Issue isolated in-process HTTP requests without a blocking portal."""

    def __init__(self, application: FastAPI) -> None:
        """Store the ASGI application under test."""
        self.application = application

    def get(self, path: str, **kwargs: Any) -> Response:
        """Issue a GET request to the application."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Response:
        """Issue a POST request to the application."""
        return self.request("POST", path, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> Response:
        """Execute one request in a dedicated event loop."""
        return asyncio.run(self._request(method, path, **kwargs))

    async def _request(self, method: str, path: str, **kwargs: Any) -> Response:
        """Send one request through HTTPX ASGI transport."""
        transport = ASGITransport(app=self.application)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    def close(self) -> None:
        """Provide compatibility with clients that require explicit closing."""
