# Zulip's OpenAPI-based API documentation system is documented at
#   https://zulip.readthedocs.io/en/latest/documentation/api.html
#
# This file contains the top-level logic for testing the cURL examples
# in Zulip's API documentation; the details are in
# zerver.openapi.curl_param_value_generators.

import glob
import html
import json
import shlex
import subprocess

import markdown
from zulip import Client

from zerver.models import get_realm
from zerver.openapi import markdown_extension
from zerver.openapi.curl_param_value_generators import (
    CALLED_GENERATOR_FUNCTIONS,
    REGISTERED_GENERATOR_FUNCTIONS,
)


def test_generated_curl_examples_for_success(client: Client) -> None:
    authentication_line = f"{client.email}:{client.api_key}"
    # A limited Markdown engine that just processes the code example syntax.
    realm = get_realm("zulip")
    md_engine = markdown.Markdown(extensions=[markdown_extension.makeExtension(
        api_url=realm.uri + "/api")])

    # We run our curl tests in alphabetical order (except that we
    # delay the deactivate-user test to the very end), since we depend
    # on "add" tests coming before "remove" tests in some cases.  We
    # should try to either avoid ordering dependencies or make them
    # very explicit.
    for file_name in sorted(glob.glob("templates/zerver/api/*.md")):
        documentation_lines = open(file_name).readlines()
        for line in documentation_lines:
            # A typical example from the Markdown source looks like this:
            #     {generate_code_example(curl, ...}
            if not line.startswith("{generate_code_example(curl"):
                continue
            # To do an end-to-end test on the documentation examples
            # that will be actually shown to users, we use the
            # Markdown rendering pipeline to compute the user-facing
            # example, and then run that to test it.
            curl_command_html = md_engine.convert(line.strip())
            unescaped_html = html.unescape(curl_command_html)
            curl_command_text = unescaped_html[len("<p><code>curl\n"):-len("</code></p>")]

            curl_command_text = curl_command_text.replace(
                "BOT_EMAIL_ADDRESS:BOT_API_KEY", authentication_line)

            print("Testing {} ...".format(curl_command_text.split("\n")[0]))

            # Turn the text into an arguments list.
            generated_curl_command = [
                x for x in shlex.split(curl_command_text) if x != "\n"]

            response_json = None
            response = None
            try:
                # We split this across two lines so if curl fails and
                # returns non-JSON output, we'll still print it.
                response_json = subprocess.check_output(generated_curl_command).decode('utf-8')
                response = json.loads(response_json)
                assert(response["result"] == "success")
            except (AssertionError, Exception):
                error_template = """
Error verifying the success of the API documentation curl example.

File: {file_name}
Line: {line}
Curl command:
{curl_command}
Response:
{response}

This test is designed to check each generate_code_example(curl) instance in the
API documentation for success. If this fails then it means that the curl example
that was generated was faulty and when tried, it resulted in an unsuccessful
response.

Common reasons for why this could occur:
    1. One or more example values in zerver/openapi/zulip.yaml for this endpoint
       do not line up with the values in the test database.
    2. One or more mandatory parameters were included in the "exclude" list.

To learn more about the test itself, see zerver/openapi/test_curl_examples.py.
"""
                print(error_template.format(
                    file_name=file_name,
                    line=line,
                    curl_command=generated_curl_command,
                    response=response_json if response is None else json.dumps(response, indent=4)))
                raise

    if REGISTERED_GENERATOR_FUNCTIONS != CALLED_GENERATOR_FUNCTIONS:
        raise Exception("Some registered generator functions were not called:\n"
                        " " + str(REGISTERED_GENERATOR_FUNCTIONS - CALLED_GENERATOR_FUNCTIONS))
