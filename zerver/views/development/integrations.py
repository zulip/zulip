import os
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import orjson
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.test import Client

from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_bool
from zerver.lib.webhooks.common import get_fixture_http_headers, standardize_headers
from zerver.models import UserProfile, get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")


def get_webhook_integrations() -> List[str]:
    return [integration.name for integration in WEBHOOK_INTEGRATIONS]


def get_valid_integration_name(name: str) -> Optional[str]:
    for integration_name in get_webhook_integrations():
        if name == integration_name:
            return integration_name
    return None


def dev_panel(request: HttpRequest) -> HttpResponse:
    integrations = get_webhook_integrations()
    bots = UserProfile.objects.filter(is_bot=True, bot_type=UserProfile.INCOMING_WEBHOOK_BOT)
    context = {
        "integrations": integrations,
        "bots": bots,
        # We set isolated_page to avoid clutter from footer/header.
        "isolated_page": True,
    }
    return render(request, "zerver/development/integrations_dev_panel.html", context)


def send_webhook_fixture_message(
    url: str, body: str, is_json: bool, custom_headers: Dict[str, Any]
) -> "TestHttpResponse":
    client = Client()
    realm = get_realm("zulip")
    standardized_headers = standardize_headers(custom_headers)
    http_host = standardized_headers.pop("HTTP_HOST", realm.host)
    if is_json:
        content_type = standardized_headers.pop("HTTP_CONTENT_TYPE", "application/json")
    else:
        content_type = standardized_headers.pop("HTTP_CONTENT_TYPE", "text/plain")
    return client.post(
        url,
        body,
        content_type=content_type,
        follow=False,
        secure=False,
        headers=None,
        HTTP_HOST=http_host,
        **standardized_headers,
    )


@has_request_variables
def get_fixtures(request: HttpRequest, integration_name: str = REQ()) -> HttpResponse:
    valid_integration_name = get_valid_integration_name(integration_name)
    if not valid_integration_name:
        raise ResourceNotFoundError(f'"{integration_name}" is not a valid webhook integration.')

    fixtures = {}
    fixtures_dir = os.path.join(ZULIP_PATH, f"zerver/webhooks/{valid_integration_name}/fixtures")
    if not os.path.exists(fixtures_dir):
        msg = f'The integration "{valid_integration_name}" does not have fixtures.'
        raise ResourceNotFoundError(msg)

    for fixture in os.listdir(fixtures_dir):
        fixture_path = os.path.join(fixtures_dir, fixture)
        with open(fixture_path) as f:
            body = f.read()
        # The file extension will be used to determine the type.
        with suppress(orjson.JSONDecodeError):
            body = orjson.loads(body)

        headers_raw = get_fixture_http_headers(
            valid_integration_name, "".join(fixture.split(".")[:-1])
        )

        def fix_name(header: str) -> str:  # nocoverage
            if header.startswith("HTTP_"):  # HTTP_ is a prefix intended for Django.
                return header[len("HTTP_") :]
            return header

        headers = {fix_name(k): v for k, v in headers_raw.items()}
        fixtures[fixture] = {"body": body, "headers": headers}

    return json_success(request, data={"fixtures": fixtures})


@has_request_variables
def check_send_webhook_fixture_message(
    request: HttpRequest,
    url: str = REQ(),
    body: str = REQ(),
    is_json: bool = REQ(json_validator=check_bool),
    custom_headers: str = REQ(),
) -> HttpResponseBase:
    try:
        custom_headers_dict = orjson.loads(custom_headers)
    except orjson.JSONDecodeError as ve:  # nocoverage
        raise JsonableError(f"Custom HTTP headers are not in a valid JSON format. {ve}")  # nolint

    response = send_webhook_fixture_message(url, body, is_json, custom_headers_dict)
    if response.status_code == 200:
        responses = [{"status_code": response.status_code, "message": response.content.decode()}]
        return json_success(request, data={"responses": responses})
    else:
        return response


@has_request_variables
def send_all_webhook_fixture_messages(
    request: HttpRequest, url: str = REQ(), integration_name: str = REQ()
) -> HttpResponse:
    valid_integration_name = get_valid_integration_name(integration_name)
    if not valid_integration_name:  # nocoverage
        raise ResourceNotFoundError(f'"{integration_name}" is not a valid webhook integration.')

    fixtures_dir = os.path.join(ZULIP_PATH, f"zerver/webhooks/{valid_integration_name}/fixtures")
    if not os.path.exists(fixtures_dir):
        msg = f'The integration "{valid_integration_name}" does not have fixtures.'
        raise ResourceNotFoundError(msg)

    responses = []
    for fixture in os.listdir(fixtures_dir):
        fixture_path = os.path.join(fixtures_dir, fixture)
        with open(fixture_path) as f:
            content = f.read()
        x = fixture.split(".")
        fixture_name, fixture_format = "".join(_ for _ in x[:-1]), x[-1]
        headers = get_fixture_http_headers(valid_integration_name, fixture_name)
        is_json = fixture_format == "json"
        response = send_webhook_fixture_message(url, content, is_json, headers)
        responses.append(
            {
                "status_code": response.status_code,
                "fixture_name": fixture,
                "message": response.content.decode(),
            }
        )
    return json_success(request, data={"responses": responses})
