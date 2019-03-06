from email import message_from_binary_file
from email.message import Message
from email.mime.text import MIMEText

from django.core.mail import get_connection
from django.core.management.base import CommandParser
from django.conf import settings

from zerver.lib.create_user import create_user_profile
from zerver.lib.email_helpers import get_message_part_by_type
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserPGP, UserProfile, get_realm, get_user
from zerver.lib.pgp import pgp_sign_and_encrypt, PGPEmailMessage

from typing import Optional

import os
import ujson

class Command(ZulipBaseCommand):
    help = """
Send specified email from a fixture file to the recipient
Example:
./manage.py send_to_email_mirror --fixture=zerver/tests/fixtures/emails/filename --recipient=foo@zulip.com

"""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('-f', '--fixture',
                            dest='fixture',
                            type=str,
                            help='The path to the email message you\'d like to send.')
        parser.add_argument('-r', '--recipient',
                            dest='recipient',
                            type=str,
                            help='Address of the recipient')
        parser.add_argument('-k', '--public-key',
                            dest='public_key',
                            type=str,
                            help='The path to the file with the recipient public key, '
                                 'if you want the message to be encrypted.')
        parser.add_argument('-s', '--sign',
                            dest='sign',
                            action='store_true',
                            help='Set this flag if you want the message to be signed.')
        parser.add_argument('-d', '--delete-if-exists',
                            dest='delete',
                            action='store_true',
                            help='Set this flag to delete the user if one with the email '
                                 'specified in --recipient already exists.\n'
                                 'Exercise caution when using this flag.')
        parser.add_argument('-b', '--backend',
                            dest='backend',
                            type=str,
                            help='Specify which Django email backend to use. Some examples '
                            ' are smtp, locmem, console. The default backend is smtp.')

    def handle(self, **options: str) -> None:
        if settings.PRODUCTION:
            self.print_help("This command is not meant to be run in production.")
            exit(1)
        if options['recipient'] is None:
            self.print_help('./manage.py', 'dev_send_pgp_email')
            exit(1)

        want_signature = True if options['sign'] else False

        if options['public_key'] is not None:
            with open(options['public_key']) as fp:
                public_key = fp.read()
        else:
            public_key = None

        realm = get_realm("zulip")
        try:
            dummy_user = get_user(options['recipient'], realm)  # type: Optional[UserProfile]
        except UserProfile.DoesNotExist:
            dummy_user = None

        if dummy_user:
            print("User with this email already in the database...")
            if options['delete']:
                print("Deleting the user.")
                dummy_user.delete()
            else:
                print("Exiting. Use the --delete-if-exists flag "
                      "if you want to delete the user.")
                exit(1)

        if options['fixture'] is None:
            print("No --fixture specified. Exiting.")
            exit(0)

        full_fixture_path = os.path.join(settings.DEPLOY_ROOT, options['fixture'])
        message = self._parse_email_fixture(full_fixture_path)
        email = self.convert_email_to_django_email(message)
        if email is None:
            print("Failed to convert to PGPEmailMessage. Unsupported format.")
            exit(1)

        dummy_user = create_user_profile(realm, options['recipient'],
                                         password=None, active=True, bot_type=None,
                                         full_name="Email Dummy", short_name="Email Dummy",
                                         bot_owner=None, is_mirror_dummy=False,
                                         tos_version=None, timezone="")
        dummy_user.want_signed_emails = want_signature
        dummy_user.save()

        if public_key:
            self._prepare_pgp(dummy_user, public_key)
            dummy_user.want_encrypted_emails = True
            dummy_user.save()

        emails = pgp_sign_and_encrypt(email, [dummy_user])
        dummy_user.delete()

        if options['backend']:
            backend = 'django.core.mail.backends.' + options['backend'] + '.EmailBackend'
        # We want to actually send the email, so the default backend
        # for DEVELOPMENT won't work.
        else:
            backend = 'django.core.mail.backends.smtp.EmailBackend'

        with get_connection(backend) as connection:
            for mail in emails:
                mail.connection = connection
                if mail.send():
                    print("Email sent succesfully to %s." % (mail.to))
                else:
                    print("Failed to send email to %s." % (mail.to))

    def convert_email_to_django_email(self, message: Optional[Message]) -> Optional[PGPEmailMessage]:
        # Convert email.message.Message object to PGPEmailMessage
        if message is None:
            return None

        plain_body = get_message_part_by_type(message, "text/plain")
        if plain_body is None:
            return None

        email = PGPEmailMessage(subject=message['Subject'], body=plain_body)
        html_body = get_message_part_by_type(message, "text/html")
        if html_body is not None:
            email.attach_alternative(html_body, "text/html")

        return email

    def _prepare_pgp(self, user: UserProfile, public_key: str) -> None:
        user_pgp = UserPGP(user_profile=user, public_key=public_key)
        user_pgp.save()

    def _does_fixture_path_exist(self, fixture_path: str) -> bool:
        return os.path.exists(fixture_path)

    def _parse_email_json_fixture(self, fixture_path: str) -> Message:
        with open(fixture_path) as fp:
            json_content = ujson.load(fp)[0]

        message = MIMEText(json_content['body'])
        message['From'] = json_content['from']
        message['Subject'] = json_content['subject']
        return message

    def _parse_email_fixture(self, fixture_path: str) -> Optional[Message]:
        if not self._does_fixture_path_exist(fixture_path):
            print('Fixture {} does not exist'.format(fixture_path))
            return None

        if fixture_path.endswith('.json'):
            message = self._parse_email_json_fixture(fixture_path)
        else:
            with open(fixture_path, "rb") as fp:
                message = message_from_binary_file(fp)

        return message
