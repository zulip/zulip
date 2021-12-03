import os

import orjson
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")


def markdown_panel(request: HttpRequest) -> HttpResponse:
    fixture_names = []
    with open(
        os.path.join(ZULIP_PATH, "zerver/tests/fixtures/markdown_test_cases.json"), "rb"
    ) as f:
        data = orjson.loads(f.read())["regular_tests"]
        for test in data:
            fixture_names.append(test["name"])

    fixture_names = sorted(fixture_names, key=str.lower)
    context = {
        # We set isolated_page to avoid clutter from footer/header.
        "fixture_names": fixture_names,
        "isolated_page": True,
        "page_params": {"login_page": settings.LOGIN_URL},
    }
    return render(request, "zerver/development/markdown_dev_panel.html", context)


@has_request_variables
def get_markdown_fixture(request: HttpRequest, fixture_name: str = REQ()) -> HttpResponse:
    with open(
        os.path.join(ZULIP_PATH, "zerver/tests/fixtures/markdown_test_cases.json"), "rb"
    ) as f:
        data = orjson.loads(f.read())["regular_tests"]
        for test in data:
            if fixture_name == test["name"]:
                return json_success({"test_input": test["input"]})

    return json_error(f'Markdown fixture with name: "{fixture_name}" not found!', status=404)
