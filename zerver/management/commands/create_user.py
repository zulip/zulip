import argparse
from typing import Any

from django.core.management.base import CommandError
from django.db.utils import IntegrityError

from zerver.lib.actions import do_create_user
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Create the specified user with a default initial password.

Sets tos_version=None, so that the user needs to do a ToS flow on login.

Omit both <email> and <full name> for interactive user creation.
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
                # Explicitly set tos_version=None. For servers that
                # have configured Terms of Service, this means that
                # users created via this mechanism will be prompted to
                # accept the Terms of Service on first login.
                tos_version=None,
                acting_user=None,
            )
        except IntegrityError:
            raise CommandError("User already exists.")
