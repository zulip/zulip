import glob
import json
import shlex
import subprocess
import markdown
import os

from zulip import Client
from zerver.lib.bugdown import api_code_examples
from zerver.models import get_realm
from zerver.openapi.curl_param_value_generators import REGISTERED_GENERATOR_FUNCTIONS, CALLED_GENERATOR_FUNCTIONS

exclude_list = [
    # The endpoint in these docs expect one or more param values that reflects the DB state.
    # We currently get the example values from openapi specs and they don't refelect the
    # state of the DB. This results in the curl request to fail.
    'delete-message.md',
    'remove-subscriptions.md',
    'delete-stream.md',
    'create-user-group.md',
    'update-user-group.md',
    'delete-user-group.md',
    'update-stream.md',
    # Endpoint can be called only by administrators.
    'create-user.md',
    'add-linkifiers.md',
    'remove-linkifiers.md',
    # Endpoint does not accept bot requests
    'get-user-groups.md',
    'update-notification-settings.md',
    # Example files do not exist
    'upload-custom-emoji.md',
    'upload-file.md',
]

def test_generated_curl_examples_for_success(client: Client) -> None:
    authentication_line = "{}:{}".format(client.email, client.api_key)
    # A limited markdown engine that just processes the code example syntax.
    realm = get_realm("zulip")
    md_engine = markdown.Markdown(extensions=[api_code_examples.makeExtension(
        api_url=realm.uri + "/api")])

    for file_name in glob.glob("templates/zerver/api/*.md"):
        if os.path.basename(file_name) in exclude_list:
            print("Skipping", file_name)
            continue
        documentation_lines = open(file_name, "r").readlines()
        for line in documentation_lines:
            # A typical example from the markdown source looks like this:
            #     {generate_code_example(curl, ...}
            if not line.startswith("{generate_code_example(curl"):
                continue
            # To do an end-to-end test on the documentation examples
            # that will be actually shown to users, we use the
            # markdown rendering pipeline to compute the user-facing
            # example, and then run that to test it.
            curl_command_html = md_engine.convert(line.strip())
            curl_command_text = curl_command_html[len("<p><code>curl\n"):-len("</code></p>")]

            curl_command_text = curl_command_text.replace(
                "BOT_EMAIL_ADDRESS:BOT_API_KEY", authentication_line)

            print("Testing %s ..." % (curl_command_text.split("\n")[0],))

            # Turn the text into an arguments list.
            generated_curl_command = [
                x for x in shlex.split(curl_command_text) if x != "\n"]

            response = None
            try:
                # We split this across two lines so if curl fails and
                # returns non-JSON output, we'll still print it.
                response = subprocess.check_output(generated_curl_command).decode('utf-8')
                response = json.loads(response)
                assert(response["result"] == "success")
            except (AssertionError, Exception):
                error_template = """
Error verifying the success of the API documentation curl example.

File: {file_name}
Line: {line}
Curl Command:
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
                    response=json.dumps(response, indent=4)))
                raise

    if REGISTERED_GENERATOR_FUNCTIONS != CALLED_GENERATOR_FUNCTIONS:
        raise Exception("Some registered generator functions were not called:\n"
                        " " + str(REGISTERED_GENERATOR_FUNCTIONS - CALLED_GENERATOR_FUNCTIONS))
