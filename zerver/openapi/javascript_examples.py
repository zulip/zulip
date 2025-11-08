# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This Python file wraps the test suite for Zulip's JavaScript API
# examples and validates the responses against our OpenAPI definitions.

import json
import os
import subprocess

from zulip import Client

from zerver.openapi.openapi import validate_against_openapi_schema


def test_js_bindings(client: Client) -> None:
    os.environ["ZULIP_USERNAME"] = client.email
    os.environ["ZULIP_API_KEY"] = client.api_key
    os.environ["ZULIP_REALM"] = client.base_url.removesuffix("/api/")

    output = subprocess.check_output(
        args=["node", "--unhandled-rejections=strict", "zerver/openapi/javascript_examples.js"],
        text=True,
    )
    endpoint_responses = json.loads(output)

    for response_data in endpoint_responses:
        print(f"Testing javascript example: {response_data['name']} ...")
        validate_against_openapi_schema(
            response_data["result"],
            response_data["endpoint"],
            response_data["method"],
            response_data["status_code"],
        )

    print("JavaScript examples validated.")
