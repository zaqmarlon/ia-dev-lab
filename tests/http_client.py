"""Synchronous test facade over HTTPX's in-process ASGI transport."""

import asyncio
from typing import Any

import httpx


class ASGITestClient:
    """Issue isolated in-process requests without a background portal thread."""

    def __init__(self, application: Any) -> None:
        """Store the ASGI application under test."""
        self.application = application

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Execute one ASGI request and return its response."""
        async def send() -> httpx.Response:
            """Send the request through an ephemeral asynchronous client."""
            transport = httpx.ASGITransport(app=self.application)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Execute a GET request."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Execute a POST request."""
        return self.request("POST", path, **kwargs)

    def close(self) -> None:
        """Complete the synchronous client lifecycle."""
