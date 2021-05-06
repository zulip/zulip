from typing import Any

import requests
import responses

from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.test_classes import ZulipTestCase


class RequestMockWithTimeoutAsHeader(responses.RequestsMock):
    def _on_request(
        self,
        adapter: requests.adapters.HTTPAdapter,
        request: requests.PreparedRequest,
        **kwargs: Any,
    ) -> requests.Response:
        if kwargs.get("timeout") is not None:
            request.headers["X-Timeout"] = kwargs["timeout"]
        return super()._on_request(  # type: ignore[misc]  # This is an undocumented internal API
            adapter,
            request,
            **kwargs,
        )


class TestOutgoingHttp(ZulipTestCase):
    def test_timeouts(self) -> None:
        with RequestMockWithTimeoutAsHeader() as mock_requests:
            mock_requests.add(responses.GET, "http://example.com/")
            OutgoingSession(timeout=17).get("http://example.com/")
            self.assertEqual(len(mock_requests.calls), 1)
            self.assertEqual(mock_requests.calls[0].request.headers["X-Timeout"], 17)

        with RequestMockWithTimeoutAsHeader() as mock_requests:
            mock_requests.add(responses.GET, "http://example.com/")
            OutgoingSession(timeout=17).get("http://example.com/", timeout=42)
            self.assertEqual(len(mock_requests.calls), 1)
            self.assertEqual(mock_requests.calls[0].request.headers["X-Timeout"], 42)
