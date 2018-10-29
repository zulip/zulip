from typing import Any, Dict

class APIRequestor:
    def interpret_response(self, http_body: str, http_status: int, http_headers: Dict[str, Any]) -> None:
        ...
