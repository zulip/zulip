from typing import Any, Dict, Optional

import requests
from urllib3 import HTTPResponse


class OutgoingSession(requests.Session):
    def __init__(self, timeout: int, headers: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        outgoing_adapter = OutgoingHTTPAdapter(timeout=timeout)
        self.mount("http://", outgoing_adapter)
        self.mount("https://", outgoing_adapter)


class OutgoingHTTPAdapter(requests.adapters.HTTPAdapter):
    timeout: int

    def __init__(self, timeout: int, *args: Any, **kwargs: Any) -> None:
        self.timeout = timeout
        super().__init__(*args, *kwargs)

    def send(self, *args: Any, **kwargs: Any) -> HTTPResponse:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)
