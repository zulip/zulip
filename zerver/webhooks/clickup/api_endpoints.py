import re
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

import requests
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.lib.exceptions import ErrorCode, WebhookError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.webhooks.clickup import EventItemType


class APIUnavailableCallBackError(WebhookError):
    """Intended as an exception for when an integration
    couldn't reach external API server when calling back
    from Zulip app.

    Exception when callback request has timed out or received
    connection error.
    """

    code = ErrorCode.REQUEST_TIMEOUT
    http_status_code = 200
    data_fields = ["webhook_name"]

    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    @override
    def msg_format() -> str:
        return _("{webhook_name} integration couldn't reach an external API service; ignoring")


class BadRequestCallBackError(WebhookError):
    """Intended as an exception for when an integration
    makes a bad request to external API server.

    Exception when callback request has an invalid format.
    """

    code = ErrorCode.BAD_REQUEST
    http_status_code = 200
    data_fields = ["webhook_name", "error_detail"]

    def __init__(self, error_detail: Optional[Union[str, int]]) -> None:
        super().__init__()
        self.error_detail = error_detail

    @staticmethod
    @override
    def msg_format() -> str:
        return _(
            "{webhook_name} integration tries to make a bad outgoing request: {error_detail}; ignoring"
        )


class ClickUpSession(OutgoingSession):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="clickup", timeout=5, **kwargs)  # nocoverage


def verify_url_path(path: str) -> bool:
    parts = path.split("/")
    if len(parts) < 2 or parts[0] not in EventItemType.as_list() or parts[1] == "":
        return False
    pattern = r"^[a-zA-Z0-9_-]+$"
    match = re.match(pattern, parts[1])
    return match is not None and match.group() == parts[1]


def make_clickup_request(path: str, api_key: str) -> Dict[str, Any]:
    if verify_url_path(path) is False:
        raise BadRequestCallBackError("Invalid path")
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
    except (requests.ConnectionError, requests.Timeout):
        raise APIUnavailableCallBackError
    except requests.HTTPError as e:
        raise BadRequestCallBackError(e.response.status_code)

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
