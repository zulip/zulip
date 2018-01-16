
import os

import ujson
from django.conf import settings
from django.core.management.base import CommandParser
from django.test import Client

from zerver.lib.management import ZulipBaseCommand
from zerver.models import get_realm

class Command(ZulipBaseCommand):
    help = """
Create webhook message based on given fixture
Example:
./manage.py send_webhook_fixture_message \
    [--realm=zulip] \
    --fixture=zerver/webhooks/integration/fixtures/name.json \
    '--url=/api/v1/external/integration?stream=stream_name&api_key=api_key'

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

        self.add_realm_args(parser, help="Specify which realm/subdomain to connect to; default is zulip")

    def handle(self, **options: str) -> None:
        if options['fixture'] is None or options['url'] is None:
            self.print_help('./manage.py', 'send_webhook_fixture_message')
            exit(1)

        full_fixture_path = os.path.join(settings.DEPLOY_ROOT, options['fixture'])

        if not self._does_fixture_path_exist(full_fixture_path):
            print('Fixture {} does not exist'.format(options['fixture']))
            exit(1)

        json = self._get_fixture_as_json(full_fixture_path)
        realm = self.get_realm(options)
        if realm is None:
            realm = get_realm("zulip")

        client = Client()
        result = client.post(options['url'], json, content_type="application/json",
                             HTTP_HOST=realm.host)
        if result.status_code != 200:
            print('Error status %s: %s' % (result.status_code, result.content))
            exit(1)

    def _does_fixture_path_exist(self, fixture_path: str) -> bool:
        return os.path.exists(fixture_path)

    def _get_fixture_as_json(self, fixture_path: str) -> str:
        return ujson.dumps(ujson.loads(open(fixture_path).read()))
