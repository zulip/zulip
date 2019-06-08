import os
import ujson
from typing import Union, Dict

from django.conf import settings
from django.core.management.base import CommandParser
from django.test import Client

from zerver.lib.management import ZulipBaseCommand, CommandError
from zerver.models import get_realm

def parse_headers(custom_headers: Union[None, str]) -> Union[None, Dict[str, str]]:
    """ The main aim of this method is be to convert regular HTTP headers into a format that
    Django prefers. Note: This function throws a ValueError and thus it should be used in a
    try/except block. """
    headers = {}
    if not custom_headers:
        return None
    custom_headers_dict = ujson.loads(custom_headers)
    for header in custom_headers_dict:
        if len(header.split(" ")) > 1:
            raise ValueError("custom header '%s' contains a space." % (header,))
        new_header = header.upper().replace("-", "_")
        if new_header not in ["CONTENT_TYPE", "CONTENT_LENGTH"]:
            new_header = "HTTP_" + new_header
        headers[new_header] = str(custom_headers_dict[header])
    return headers

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
        parser.add_argument('-f', '--fixture',
                            dest='fixture',
                            type=str,
                            help='The path to the fixture you\'d like to send '
                                 'into Zulip')

        parser.add_argument('-u', '--url',
                            dest='url',
                            type=str,
                            help='The url on your Zulip server that you want '
                                 'to post the fixture to')

        parser.add_argument('-H', '--custom-headers',
                            dest='custom-headers',
                            type=str,
                            help='The headers you want to provide along with '
                                 'your mock request to Zulip.')

        self.add_realm_args(parser, help="Specify which realm/subdomain to connect to; default is zulip")

    def parse_headers(self, custom_headers: Union[None, str]) -> Union[None, Dict[str, str]]:
        try:
            return parse_headers(custom_headers)
        except ValueError as ve:
            raise CommandError('Encountered an error while attempting to parse custom headers: {}\n'
                               'Note: all strings must be enclosed within "" instead of \'\''.format(ve))

    def handle(self, **options: str) -> None:
        if options['fixture'] is None or options['url'] is None:
            self.print_help('./manage.py', 'send_webhook_fixture_message')
            raise CommandError

        full_fixture_path = os.path.join(settings.DEPLOY_ROOT, options['fixture'])

        if not self._does_fixture_path_exist(full_fixture_path):
            raise CommandError('Fixture {} does not exist'.format(options['fixture']))

        headers = self.parse_headers(options['custom-headers'])
        json = self._get_fixture_as_json(full_fixture_path)
        realm = self.get_realm(options)
        if realm is None:
            realm = get_realm("zulip")

        client = Client()
        if headers:
            result = client.post(options['url'], json, content_type="application/json",
                                 HTTP_HOST=realm.host, **headers)
        else:
            result = client.post(options['url'], json, content_type="application/json",
                                 HTTP_HOST=realm.host)
        if result.status_code != 200:
            raise CommandError('Error status %s: %s' % (result.status_code, result.content))

    def _does_fixture_path_exist(self, fixture_path: str) -> bool:
        return os.path.exists(fixture_path)

    def _get_fixture_as_json(self, fixture_path: str) -> str:
        return ujson.dumps(ujson.loads(open(fixture_path).read()))
