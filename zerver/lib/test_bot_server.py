"""
Test bot HTTP server for integration testing.

This module provides a simple HTTP server that acts as a test bot,
allowing integration tests to verify the actual HTTP payload format
and response handling without mocking.

Usage:
    with test_bot_server() as bot:
        # bot.url is the URL to configure in the webhook bot
        # bot.set_response({"content": "Hello!"})
        # ... run your test ...
        # bot.get_requests() returns all received requests
"""

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class TestBotRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the test bot server."""

    # These are set by TestBotServer before the server starts
    server_instance: "TestBotServer"

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass

    def do_POST(self) -> None:
        """Handle POST requests from the BotInteractionWorker."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request_data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            request_data = {"raw_body": body.decode("utf-8", errors="replace")}

        # Store the request for test assertions
        self.server_instance._store_request(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": request_data,
                "timestamp": time.time(),
            }
        )

        # Get the response to send
        response_data, status_code, delay = self.server_instance._get_response()

        # Simulate slow responses if delay is set
        if delay > 0:
            time.sleep(delay)

        # Send response
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if response_data is not None:
            response_body = json.dumps(response_data)
            self.wfile.write(response_body.encode("utf-8"))


class TestBotServer:
    """
    A test bot HTTP server for integration testing.

    Provides:
    - A real HTTP server that receives requests
    - Storage for all received requests (for assertions)
    - Configurable responses (including errors and delays)
    - Thread-safe operation
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """
        Initialize the test bot server.

        Args:
            host: Host to bind to (default: 127.0.0.1)
            port: Port to bind to (default: 0 = auto-assign)
        """
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        # Response configuration
        self._response_data: dict[str, Any] | None = None
        self._response_status: int = 200
        self._response_delay: float = 0.0

        # Event for waiting on requests
        self._request_received = threading.Event()

    @property
    def url(self) -> str:
        """Get the base URL of the test bot server."""
        if self._server is None:
            raise RuntimeError("Server not started")
        return f"http://{self._host}:{self._server.server_address[1]}/"

    @property
    def port(self) -> int:
        """Get the port the server is listening on."""
        if self._server is None:
            raise RuntimeError("Server not started")
        return self._server.server_address[1]

    def start(self) -> None:
        """Start the test bot server in a background thread."""
        # Find an available port if port is 0
        if self._port == 0:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self._host, 0))
                self._port = s.getsockname()[1]

        # Create the server
        self._server = HTTPServer((self._host, self._port), TestBotRequestHandler)

        # Set the server instance on the handler class so it can access our state
        TestBotRequestHandler.server_instance = self

        # Start the server in a background thread
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        # Wait for server to be ready
        self._wait_for_server()

    def _wait_for_server(self, timeout: float = 5.0) -> None:
        """Wait for the server to be ready to accept connections."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    s.connect((self._host, self.port))
                    return
            except (ConnectionRefusedError, OSError):
                time.sleep(0.01)
        raise RuntimeError("Server failed to start within timeout")

    def stop(self) -> None:
        """Stop the test bot server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def reset(self) -> None:
        """Reset the server state (requests and response config)."""
        with self._lock:
            self._requests = []
            self._response_data = None
            self._response_status = 200
            self._response_delay = 0.0
            self._request_received.clear()

    def set_response(
        self,
        data: dict[str, Any] | None = None,
        status: int = 200,
        delay: float = 0.0,
    ) -> None:
        """
        Configure the response the server will send.

        Args:
            data: JSON response body (None for empty response)
            status: HTTP status code
            delay: Delay in seconds before sending response
        """
        with self._lock:
            self._response_data = data
            self._response_status = status
            self._response_delay = delay

    def get_requests(self) -> list[dict[str, Any]]:
        """Get all received requests."""
        with self._lock:
            return list(self._requests)

    def get_last_request(self) -> dict[str, Any] | None:
        """Get the most recent request, or None if no requests received."""
        with self._lock:
            return self._requests[-1] if self._requests else None

    def wait_for_request(self, timeout: float = 5.0) -> bool:
        """
        Wait for a request to be received.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if a request was received, False if timeout
        """
        return self._request_received.wait(timeout=timeout)

    def _store_request(self, request: dict[str, Any]) -> None:
        """Store a received request (called by the handler)."""
        with self._lock:
            self._requests.append(request)
            self._request_received.set()

    def _get_response(self) -> tuple[dict[str, Any] | None, int, float]:
        """Get the configured response (called by the handler)."""
        with self._lock:
            return self._response_data, self._response_status, self._response_delay


@contextmanager
def test_bot_server(
    host: str = "127.0.0.1",
    port: int = 0,
) -> Iterator[TestBotServer]:
    """
    Context manager that runs a test bot server.

    Usage:
        with test_bot_server() as bot:
            # Create a webhook bot pointing to bot.url
            bot.set_response({"content": "Hello!"})
            # ... trigger interaction ...
            requests = bot.get_requests()
            assert len(requests) == 1

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to bind to (default: 0 = auto-assign)

    Yields:
        TestBotServer instance
    """
    server = TestBotServer(host=host, port=port)
    server.start()
    try:
        yield server
    finally:
        server.stop()
