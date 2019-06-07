import os
import ujson
from typing import List

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.test import Client

from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.models import UserProfile, get_realm
from zerver.management.commands.send_webhook_fixture_message import parse_headers
from zerver.lib.webhooks.common import get_http_headers


ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../')


def get_webhook_integrations() -> List[str]:
    return [integration.name for integration in WEBHOOK_INTEGRATIONS]


def dev_panel(request: HttpRequest) -> HttpResponse:
    integrations = get_webhook_integrations()
    bots = UserProfile.objects.filter(is_bot=True, bot_type=UserProfile.INCOMING_WEBHOOK_BOT)
    context = {"integrations": integrations, "bots": bots}
    return render(request, "zerver/integrations/development/dev_panel.html", context)

def send_webhook_fixture_message(url: str=REQ(),
                                 body: str=REQ(),
                                 is_json: bool=REQ(),
                                 custom_headers: str=REQ()) -> HttpResponse:
    client = Client()
    realm = get_realm("zulip")
    try:
        headers = parse_headers(custom_headers)
    except ValueError as ve:
        return json_error("Custom HTTP headers are not in a valid JSON format. {}".format(ve))  # nolint
    if not headers:
        headers = {}
    http_host = headers.pop("HTTP_HOST", realm.host)
    if is_json:
        content_type = headers.pop("HTTP_CONTENT_TYPE", "application/json")
    else:
        content_type = headers.pop("HTTP_CONTENT_TYPE", "text/plain")
    return client.post(url, body, content_type=content_type, HTTP_HOST=http_host, **headers)

@has_request_variables
def get_fixtures(request: HttpResponse,
                 integration_name: str=REQ()) -> HttpResponse:
    integrations = get_webhook_integrations()
    if integration_name not in integrations:
        return json_error("\"{integration_name}\" is not a valid webhook integration.".format(
            integration_name=integration_name), status=404)

    fixtures = {}
    fixtures_dir = os.path.join(ZULIP_PATH, "zerver/webhooks/{integration_name}/fixtures".format(
        integration_name=integration_name))
    if not os.path.exists(fixtures_dir):
        msg = ("The integration \"{integration_name}\" does not have fixtures.").format(
            integration_name=integration_name)
        return json_error(msg, status=404)

    for fixture in os.listdir(fixtures_dir):
        fixture_path = os.path.join(fixtures_dir, fixture)
        body = open(fixture_path).read()
        try:
            body = ujson.loads(body)
        except ValueError:
            pass  # The file extension will be used to determine the type.
        headers_raw = get_http_headers(integration_name, "".join(fixture.split(".")[:-1]))
        # remove the file extention
        headers = {}
        for header in headers_raw:
            if header.startswith("HTTP_"):  # HTTP_ is a prefix intended for Django.
                headers[header.lstrip("HTTP_")] = headers_raw[header]
            else:
                headers[header] = headers_raw[header]
        fixtures[fixture] = {"body": body, "headers": headers}

    return json_success({"fixtures": fixtures})


@has_request_variables
def check_send_webhook_fixture_message(request: HttpRequest,
                                       url: str=REQ(),
                                       body: str=REQ(),
                                       is_json: bool=REQ(),
                                       custom_headers: str=REQ()) -> HttpResponse:
    response = send_webhook_fixture_message(url, body, is_json, custom_headers)
    if response.status_code == 200:
        responses = [{"status_code": response.status_code,
                      "message": response.content}]
        return json_success({"responses": responses})
    else:
        return response


@has_request_variables
def send_all_webhook_fixture_messages(request: HttpRequest,
                                      url: str=REQ(),
                                      custom_headers: str=REQ(),
                                      integration_name: str=REQ()) -> HttpResponse:
    fixtures_dir = os.path.join(ZULIP_PATH, "zerver/webhooks/{integration_name}/fixtures".format(
        integration_name=integration_name))
    if not os.path.exists(fixtures_dir):
        msg = ("The integration \"{integration_name}\" does not have fixtures.").format(
            integration_name=integration_name)
        return json_error(msg, status=404)

    responses = []
    for fixture in os.listdir(fixtures_dir):
        fixture_path = os.path.join(fixtures_dir, fixture)
        content = open(fixture_path).read()
        fixture_format = fixture.split(".")[-1]
        if fixture_format == "json":
            is_json = True
        else:
            is_json = False
        response = send_webhook_fixture_message(url, content, is_json, custom_headers)
        responses.append({"status_code": response.status_code,
                          "fixture_name": fixture,
                          "message": response.content})
    return json_success({"responses": responses})
