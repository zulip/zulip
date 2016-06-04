from __future__ import absolute_import
from __future__ import print_function

from typing import Any

import os
import ujson
from optparse import make_option

from django.test import Client
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = """
Create webhook message based on given fixture
Example:
./manage.py send_webhook_fixture_message \
    --fixture=zerver/fixtures/integration/fixture.json \
    '--url=/api/v1/external/integration?stream=stream_name&api_key=api_key'

"""

    option_list = BaseCommand.option_list + (
        make_option('-f', '--fixture',
                    dest='fixture',
                    type='str',
                    help='The path to the fixture you\'d like to send into Zulip'),
        make_option('-u', '--url',
                    dest='url',
                    type='str',
                    help='The url on your Zulip server that you want to post the fixture to'),
        )

    def handle(self, **options):
        # type: (*Any, **str) -> None
        if options['fixture'] is None or options['url'] is None:
            self.print_help('python manage.py', 'send_webhook_fixture_message')
            exit(1)

        full_fixture_path = os.path.join(settings.DEPLOY_ROOT, options['fixture'])

        if not self._does_fixture_path_exist(full_fixture_path):
            print('Fixture {} does not exist'.format(options['fixture']))
            exit(1)

        json = self._get_fixture_as_json(full_fixture_path)
        client = Client()
        client.post(options['url'], json, content_type="application/json")

    def _does_fixture_path_exist(self, fixture_path):
        # type: (str) -> bool
        return os.path.exists(fixture_path)

    def _get_fixture_as_json(self, fixture_path):
        # type: (str) -> str
        return ujson.dumps(ujson.loads(open(fixture_path).read()))
