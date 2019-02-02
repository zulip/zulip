
import os
import email
import ujson

from email.message import Message
from email.mime.text import MIMEText

from django.conf import settings
from django.core.management.base import CommandParser

from zerver.lib.actions import encode_email_address
from zerver.lib.email_mirror import process_message
from zerver.lib.management import ZulipBaseCommand

from zerver.models import Realm, get_stream, get_realm

# This command loads an email from a specified file and sends it
# to the email mirror. Simple emails can be passed in a JSON file,
# Look at zerver/tests/fixtures/email/1.json for an example of how
# it should look. You can also pass a file which has the raw email,
# for example by writing an email.message.Message type object
# to a file using as_string() or as_bytes() methods, or copy-pasting
# the content of "Show original" on an email in Gmail.
# See zerver/tests/fixtures/email/1.txt for a very simple example,
# but anything that the message_from_binary_file function
# from the email library can parse should work.
# Value of the TO: header doesn't matter, as it is overriden
# by the command in order for the email to be sent to the correct stream.

class Command(ZulipBaseCommand):
    help = """
Send specified email from a fixture file to the email mirror
Example:
./manage.py send_to_email_mirror --fixture=zerver/tests/fixtures/emails/filename

"""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('-f', '--fixture',
                            dest='fixture',
                            type=str,
                            help='The path to the email message you\'d like to send '
                                 'to the email mirror.\n'
                                 'Accepted formats: json or raw email file. '
                                 'See zerver/tests/fixtures/email/ for examples')
        parser.add_argument('-s', '--stream',
                            dest='stream',
                            type=str,
                            help='The name of the stream to which you\'d like to send '
                            'the message. Default: Denmark')

        self.add_realm_args(parser, help="Specify which realm to connect to; default is zulip")

    def handle(self, **options: str) -> None:
        if options['fixture'] is None:
            self.print_help('./manage.py', 'send_to_email_mirror')
            exit(1)

        if options['stream'] is None:
            stream = "Denmark"
        else:
            stream = options['stream']

        realm = self.get_realm(options)
        if realm is None:
            realm = get_realm("zulip")

        full_fixture_path = os.path.join(settings.DEPLOY_ROOT, options['fixture'])

        # parse the input email into Message type and prepare to process_message() it
        message = self._parse_email_fixture(full_fixture_path)
        self._prepare_message(message, realm, stream)

        process_message(message)

    def _does_fixture_path_exist(self, fixture_path: str) -> bool:
        return os.path.exists(fixture_path)

    def _parse_email_json_fixture(self, fixture_path: str) -> Message:
        with open(fixture_path) as fp:
            json_content = ujson.load(fp)[0]

        message = MIMEText(json_content['body'])
        message['From'] = json_content['from']
        message['Subject'] = json_content['subject']
        return message

    def _parse_email_fixture(self, fixture_path: str) -> Message:
        if not self._does_fixture_path_exist(fixture_path):
            print('Fixture {} does not exist'.format(fixture_path))
            exit(1)

        if fixture_path.endswith('.json'):
            message = self._parse_email_json_fixture(fixture_path)
        else:
            with open(fixture_path, "rb") as fp:
                message = email.message_from_binary_file(fp)

        return message

    def _prepare_message(self, message: Message, realm: Realm, stream_name: str) -> None:
        stream = get_stream(stream_name, realm)

        recipient_headers = ["X-Gm-Original-To", "Delivered-To",
                             "Resent-To", "Resent-CC", "To", "CC"]
        for header in recipient_headers:
            if header in message:
                del message[header]
                message[header] = encode_email_address(stream)
                return

        message['To'] = encode_email_address(stream)
