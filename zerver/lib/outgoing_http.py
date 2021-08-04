from typing import Any, Dict, Optional

import requests


class OutgoingSession(requests.Session):
    def __init__(self, role: str, timeout: int, headers: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        outgoing_adapter = OutgoingHTTPAdapter(role=role, timeout=timeout)
        self.mount("http://", outgoing_adapter)
        self.mount("https://", outgoing_adapter)
        if headers:
            self.headers.update(headers)


class OutgoingHTTPAdapter(requests.adapters.HTTPAdapter):
    role: str
    timeout: int

    def __init__(self, role: str, timeout: int) -> None:
        self.role = role
        self.timeout = timeout
        super().__init__()

    def send(self, *args: Any, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)

    def proxy_headers(self, proxy: str) -> Dict[str, str]:
        return {"X-Smokescreen-Role": self.role}
