from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import CommandError, ZulipBaseCommand
from zerver.lib.send_email import send_custom_email
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--entire-server', action="store_true", default=False,
                            help="Send to every user on the server. ")
        parser.add_argument('--markdown-template-path', '--path',
                            dest='markdown_template_path',
                            required=True,
                            type=str,
                            help='Path to a markdown-format body for the email')
        parser.add_argument('--subject',
                            type=str,
                            help='Subject for the email. It can be declarated in markdown file in headers')
        parser.add_argument('--from-name',
                            type=str,
                            help='From line for the email. It can be declarated in markdown file in headers')
        parser.add_argument('--reply-to',
                            type=str,
                            help='Optional reply-to line for the email')

        self.add_user_list_args(parser,
                                help="Email addresses of user(s) to send emails to.",
                                all_users_help="Send to every user on the realm.")
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: str) -> None:
        if options["entire_server"]:
            users = UserProfile.objects.filter(is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        else:
            realm = self.get_realm(options)
            try:
                users = self.get_users(options, realm, is_bot=False)
            except CommandError as error:
                if str(error) == "You have to pass either -u/--users or -a/--all-users.":
                    raise CommandError("You have to pass -u/--users or -a/--all-users or --entire-server.")
                raise error

        send_custom_email(users, options)
