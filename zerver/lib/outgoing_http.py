from typing import Any

import requests
from typing_extensions import override
from urllib3.util import Retry

from zproject.config import get_config


class OutgoingSession(requests.Session):
    def __init__(
        self,
        role: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        max_retries: int | Retry | None = None,
        proxies: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        retry: Retry | None = Retry(total=0)
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

        if proxies is None:
            proxy_host = get_config("http_proxy", "host", "localhost")
            proxy_port = get_config("http_proxy", "port", "4750")
            proxy = ""
            if proxy_host != "" and proxy_port != "":
                proxy = f"http://{proxy_host}:{proxy_port}"
                self.proxies.update(
                    {
                        "http": proxy,
                        "https": proxy,
                    }
                )
        else:
            self.proxies.update(proxies)


class OutgoingHTTPAdapter(requests.adapters.HTTPAdapter):
    role: str
    timeout: float

    def __init__(self, role: str, timeout: float, max_retries: Retry | None) -> None:
        self.role = role
        self.timeout = timeout
        super().__init__(max_retries=max_retries)

    @override
    def send(self, *args: Any, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)

    @override
    def proxy_headers(self, proxy: str) -> dict[str, str]:
        return {"X-Smokescreen-Role": self.role}
