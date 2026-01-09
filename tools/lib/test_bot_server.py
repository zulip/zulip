#!/usr/bin/env python3
"""
Standalone HTTP server that acts as a test bot for e2e testing.

This server receives bot interaction events and returns configurable responses.
It can be started independently of the test suite for debugging, or programmatically
controlled via a simple HTTP API.

Usage:
    # Start the server (runs on port 9877 by default)
    python tools/lib/test_bot_server.py

    # Start on a specific port
    python tools/lib/test_bot_server.py --port 9878

    # Start with verbose logging
    python tools/lib/test_bot_server.py --verbose

Control API:
    POST /control/reset - Clear all received requests
    POST /control/response - Set response to return for next interaction
    GET /control/requests - Get all received requests as JSON
    GET /control/health - Health check endpoint
"""

import argparse
import http.server
import json
import logging
import socketserver
import sys
import threading
from typing import Any

# Default port for e2e test bot server
DEFAULT_PORT = 9877

# Storage for received requests and configured response
_received_requests: list[dict[str, Any]] = []
_response_config: dict[str, Any] = {}
_lock = threading.Lock()

logger = logging.getLogger(__name__)


class TestBotHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the test bot server."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use logging module instead of stderr."""
        logger.info(format % args)

    def _send_json_response(self, data: dict[str, Any], status: int = 200) -> None:
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json_body(self) -> dict[str, Any] | None:
        """Read and parse JSON body from request."""
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return None
        try:
            body = self.rfile.read(int(content_length))
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse request body: %s", e)
            return None

    def do_GET(self) -> None:
        """Handle GET requests (control API)."""
        if self.path == "/control/requests":
            with _lock:
                self._send_json_response({"requests": list(_received_requests)})
        elif self.path == "/control/health":
            self._send_json_response({"status": "ok"})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        """Handle POST requests (bot interactions and control API)."""
        global _response_config

        # Control API endpoints
        if self.path == "/control/reset":
            with _lock:
                _received_requests.clear()
                _response_config = {}
            self._send_json_response({"status": "reset"})
            return

        if self.path == "/control/response":
            body = self._read_json_body()
            if body:
                with _lock:
                    _response_config = body
            self._send_json_response({"status": "configured"})
            return

        # Bot interaction endpoint (any other POST)
        body = self._read_json_body()
        if body:
            logger.info("Received bot interaction: %s", json.dumps(body, indent=2))
            with _lock:
                _received_requests.append(body)
                response = dict(_response_config)

            # Send configured response or empty 200
            if response:
                self._send_json_response(response)
            else:
                self.send_response(200)
                self.end_headers()
        else:
            self.send_error(400, "Bad Request")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Thread-per-request HTTP server."""

    allow_reuse_address = True
    daemon_threads = True


def start_server(port: int = DEFAULT_PORT, verbose: bool = False) -> ThreadedHTTPServer:
    """Start the test bot server on the specified port."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    server = ThreadedHTTPServer(("0.0.0.0", port), TestBotHandler)
    logger.info("Test bot server starting on http://0.0.0.0:%d", port)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Test bot HTTP server for e2e testing")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    server = start_server(port=args.port, verbose=args.verbose)

    try:
        print(f"Test bot server running on http://0.0.0.0:{args.port}")
        print("Control API:")
        print(f"  POST http://localhost:{args.port}/control/reset - Clear requests")
        print(f"  POST http://localhost:{args.port}/control/response - Set response")
        print(f"  GET  http://localhost:{args.port}/control/requests - Get requests")
        print(f"  GET  http://localhost:{args.port}/control/health - Health check")
        print("\nPress Ctrl+C to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
