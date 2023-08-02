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
        return os.path.exists(fixture_path)

    def _get_fixture_as_json(self, fixture_path: str) -> bytes:
        with open(fixture_path, "rb") as f:
            return orjson.dumps(orjson.loads(f.read()))
