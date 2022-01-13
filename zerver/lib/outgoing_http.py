from typing import Any, Dict, Optional, Union

import requests
from urllib3.util import Retry


class OutgoingSession(requests.Session):
    def __init__(
        self,
        role: str,
        timeout: int,
        headers: Optional[Dict[str, str]] = None,
        max_retries: Optional[Union[int, Retry]] = None,
    ) -> None:
        super().__init__()
        retry: Optional[Retry] = Retry(total=0)
        if max_retries is not None:
            if isinstance(max_retries, Retry):
                retry = max_retries
            else:
                retry = Retry(total=max_retries, backoff_factor=1)
        outgoing_adapter = OutgoingHTTPAdapter(role=role, timeout=timeout, max_retries=retry)
        self.mount("http://", outgoing_adapter)
        self.mount("https://", outgoing_adapter)
        if headers:
            self.headers.update(headers)


class OutgoingHTTPAdapter(requests.adapters.HTTPAdapter):
    role: str
    timeout: int

    def __init__(self, role: str, timeout: int, max_retries: Optional[Retry]) -> None:
        self.role = role
        self.timeout = timeout
        super().__init__(max_retries=max_retries)

    def send(self, *args: Any, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)

    def proxy_headers(self, proxy: str) -> Dict[str, str]:
        return {"X-Smokescreen-Role": self.role}
