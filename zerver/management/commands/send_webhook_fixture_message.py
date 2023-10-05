import os
from typing import Any, Dict, Optional, Union

import orjson
from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from django.test import Client

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.webhooks.common import standardize_headers
from zerver.models import get_realm


class Command(ZulipBaseCommand):
    """Create webhook message based on given fixture
    Example:
    ./manage.py send_webhook_fixture_message \
        [--realm=zulip] \
        --fixture=zerver/webhooks/integration/fixtures/name.json \
        '--url=/api/v1/external/integration?stream=stream_name&api_key=api_key'

    To pass custom headers along with the webhook message use the --custom-headers
    command line option.
    Example:
        --custom-headers='{"X-Custom-Header": "value"}'

    The format is a JSON dictionary, so make sure that the header names do
    not contain any spaces in them and that you use the precise quoting
    approach shown above.
    """
    help = """
Create webhook message based on given fixture
Example:
./manage.py send_webhook_fixture_message \
    [--realm=zulip] \
    --fixture=zerver/webhooks/integration/fixtures/name.json \
    '--url=/api/v1/external/integration?stream=stream_name&api_key=api_key'

To pass custom headers along with the webhook message use the --custom-headers
command line option.
Example:
    --custom-headers='{"X-Custom-Header": "value"}'

The format is a JSON dictionary, so make sure that the header names do
not contain any spaces in them and that you use the precise quoting
approach shown above.
"""

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command-line arguments to the parser.

        Args:
            parser (CommandParser): The argument parser.
        """
        parser.add_argument(
            "-f", "--fixture", help="The path to the fixture you'd like to send into Zulip"
        )

        parser.add_argument(
            "-u", "--url", help="The URL on your Zulip server that you want to post the fixture to"
        )

        parser.add_argument(
            "-H",
            "--custom-headers",
            help="The headers you want to provide along with your mock request to Zulip.",
        )

        self.add_realm_args(
            parser, help="Specify which realm/subdomain to connect to; default is zulip"
        )

    def parse_headers(self, custom_headers: Union[None, str]) -> Union[None, Dict[str, str]]:
        """
        Parse custom headers and return a standardized dictionary.

        This function takes a 'custom_headers' parameter, which can be either a string
        representing custom headers or None. If the 'custom_headers' parameter is
        None, an empty dictionary is returned. Otherwise, the function attempts to
        parse the 'custom_headers' string using the 'orjson.loads' function. If an
        error occurs during parsing, a 'CommandError' exception is raised with an
        error message. The error message includes the original error message from
        'orjson.JSONDecodeError' and a note about using double quotes instead of
        single quotes.
        Finally, the function calls the 'standardize_headers' function with the parsed
        'custom_headers' dictionary and returns the result.
        """
        if not custom_headers:
            return {}
        try:
            custom_headers_dict = orjson.loads(custom_headers)
        except orjson.JSONDecodeError as ve:
            raise CommandError(
                f"Encountered an error while attempting to parse custom headers: {ve}\n"
                "Note: all strings must be enclosed within \"\" instead of ''"
            )
        return standardize_headers(custom_headers_dict)

    def handle(self, *args: Any, **options: Optional[str]) -> None:
        """
        Handle function for sending a webhook fixture message.

        This function takes variable positional arguments and variable keyword arguments.
        It first checks if the 'fixture' and 'url' options are provided. If either of
        them is missing, it prints the help message and raises a CommandError.

        Then, it constructs the full path of the fixture file using the
        'settings.DEPLOY_ROOT' variable and the 'fixture' option.
        If the fixture file does not exist, it raises a CommandError.

        Next, it parses the custom headers provided in the 'custom_headers' option and
        reads the fixture file as a JSON object.

        It gets the realm associated with the options and if not found, it sets the
        realm to 'zulip'.

        Finally, it creates a 'Client' object and sends a POST request to the specified
        URL with the fixture JSON data and headers if provided.
        If the response status code is not 200, it raises a CommandError with the error
        message.
        """
        if options["fixture"] is None or options["url"] is None:
            self.print_help("./manage.py", "send_webhook_fixture_message")
            raise CommandError

        full_fixture_path = os.path.join(settings.DEPLOY_ROOT, options["fixture"])

        if not self._does_fixture_path_exist(full_fixture_path):
            raise CommandError("Fixture {} does not exist".format(options["fixture"]))

        headers = self.parse_headers(options["custom_headers"])
        json = self._get_fixture_as_json(full_fixture_path)
        realm = self.get_realm(options)
        if realm is None:
            realm = get_realm("zulip")

        client = Client()
        if headers:
            result = client.post(
                options["url"],
                json,
                content_type="application/json",
                HTTP_HOST=realm.host,
                extra=headers,
            )
        else:
            result = client.post(
                options["url"], json, content_type="application/json", HTTP_HOST=realm.host
            )
        if result.status_code != 200:
            raise CommandError(f"Error status {result.status_code}: {result.content!r}")

    def _does_fixture_path_exist(self, fixture_path: str) -> bool:
        """
        Check if the fixture path exists.

        This function takes a path string as input and returns a boolean indicating
        whether the path exists in the filesystem or not.

        Args:
            fixture_path (str): The path to the fixture file.

        Returns:
            bool: True if the fixture path exists, False otherwise.
        """
        return os.path.exists(fixture_path)

    def _get_fixture_as_json(self, fixture_path: str) -> bytes:
        """
        Get the contents of a fixture file as a JSON string.

        This method reads the fixture file located at 'fixture_path' and returns its contents
        as a JSON string in the form of bytes. The JSON string is loaded using the
        'orjson' library and then dumped back into a bytes object.

        Args:
            fixture_path (str): The path to the fixture file.

        Returns:
            bytes: The contents of the fixture file as a JSON string.
        """
        with open(fixture_path, "rb") as f:
            return orjson.dumps(orjson.loads(f.read()))
