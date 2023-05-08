import argparse
from typing import Any

from django.core.management.base import CommandError
from django.db.utils import IntegrityError

from zerver.actions.create_user import do_create_user
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """Create a new Zulip user via the command line.

Prompts the user for <email> and <full name> if not specified.

We recommend the Zulip API (https://zulip.com/api/create-user) instead
of this tool for most use cases.

If the server has Terms of Service configured, the user will be
prompted to accept the Terms of Service the first time they login.
"""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        self.add_create_user_args(parser)
        self.add_realm_args(
            parser, required=True, help="The name of the existing realm to which to add the user."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        create_user_params = self.get_create_user_params(options)

        try:
            do_create_user(
                create_user_params.email,
                create_user_params.password,
                realm,
                create_user_params.full_name,
                # Explicitly set tos_version=-1. This means that users
                # created via this mechanism would be prompted to set
                # the email_address_visibility setting on first login.
                # For servers that have configured Terms of Service,
                # users will also be prompted to accept the Terms of
                # Service on first login.
                tos_version=UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN,
                acting_user=None,
            )
        except IntegrityError:
            raise CommandError("User already exists.")
