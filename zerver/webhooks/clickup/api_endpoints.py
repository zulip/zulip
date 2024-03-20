from typing import Any
from urllib.parse import urljoin

import requests


def get_clickup_api_data(clickup_api_path: str, **kwargs: Any) -> dict[str, Any]:
    if not kwargs.get("token"):
        raise AssertionError("ClickUp API 'token' missing in kwargs")
    token = kwargs.pop("token")

    base_url = "https://api.clickup.com/api/v2/"
    api_endpoint = urljoin(base_url, clickup_api_path)
    response = requests.get(
        api_endpoint,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
        },
        params=kwargs,
    )
    if response.status_code == requests.codes.ok:
        return response.json()
    else:
        raise Exception(f"HTTP error accessing the ClickUp API. Error: {response.status_code}")
