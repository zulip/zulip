from typing import Any, Dict

import requests
from urllib.parse import urljoin
from zerver.lib.outgoing_http import OutgoingSession


class Error(Exception):
    pass


class APIUnavailableError(Error):
    pass


class BadRequestError(Error):
    pass


class ClickUpSession(OutgoingSession):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="clickup", timeout=5, **kwargs)


def make_clickup_request(path: str, api_key: str) -> Dict[str, Any]:
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": api_key,
    }

    try:
        base_url = "https://api.clickup.com/api/v2/"
        api_endpoint = urljoin(base_url, path)
        response = ClickUpSession(headers=headers).get(
            api_endpoint,
        )
        response.raise_for_status()
    except (requests.ConnectionError, requests.Timeout) as e:
        raise APIUnavailableError from e
    except requests.HTTPError as e:
        raise BadRequestError from e

    return response.json()


def get_list(api_key: str, list_id: str) -> Dict[str, Any]:
    data = make_clickup_request(f"list/{list_id}", api_key)
    return data


def get_task(api_key: str, task_id: str) -> Dict[str, Any]:
    data = make_clickup_request(f"task/{task_id}", api_key)
    return data


def get_folder(api_key: str, folder_id: str) -> Dict[str, Any]:
    data = make_clickup_request(f"folder/{folder_id}", api_key)
    return data


def get_goal(api_key: str, goal_id: str) -> Dict[str, Any]:
    data = make_clickup_request(f"goal/{goal_id}", api_key)
    return data


def get_space(api_key: str, space_id: str) -> Dict[str, Any]:
    data = make_clickup_request(f"space/{space_id}", api_key)
    return data
