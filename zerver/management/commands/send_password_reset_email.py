from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from django.db.models import QuerySet
from typing_extensions import override

from zerver.actions.users import do_send_password_reset_email
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """Send email to specified email address."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--only-never-logged-in",
            action="store_true",
            help="Filter to only users which have not accepted the TOS.",
        )
        parser.add_argument(
            "--entire-server", action="store_true", help="Send to every user on the server. "
        )
        self.add_user_list_args(
            parser,
            help="Email addresses of user(s) to send password reset emails to.",
            all_users_help="Send to every user on the realm.",
        )
        self.add_realm_args(parser)

    @override
    def handle(self, *args: Any, **options: str) -> None:
        if options["entire_server"]:
            users: QuerySet[UserProfile] = UserProfile.objects.filter(
                is_active=True, is_bot=False, is_mirror_dummy=False
            )
        else:
            realm = self.get_realm(options)
            try:
                users = self.get_users(options, realm, is_bot=False)
            except CommandError as error:
                if str(error) == "You have to pass either -u/--users or -a/--all-users.":
                    raise CommandError(
                        "You have to pass -u/--users or -a/--all-users or --entire-server."
                    )
                raise error
        if options["only_never_logged_in"]:
            users = users.filter(tos_version=-1)

        if not users.exists():
            print("No matching users!")

        self.send(users)

    def send(self, users: QuerySet[UserProfile]) -> None:
        """Sends one-use only links for resetting password to target users"""
        for user_profile in users:
            do_send_password_reset_email(
                user_profile.delivery_email, user_profile.realm, user_profile
            )
