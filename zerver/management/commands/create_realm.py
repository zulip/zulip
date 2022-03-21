import argparse
from typing import Any

from django.core.management.base import CommandError

from zerver.lib.actions import do_create_realm, do_create_user
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """\
Create a new Zulip organization (realm) via the command line.

We recommend `./manage.py generate_realm_creation_link` for most
users, for several reasons:

* Has a more user-friendly web flow for account creation.
* Manages passwords in a more natural way.
* Automatically logs the user in during account creation.

This management command is available as an alternative for situations
where one wants to script the realm creation process.

Since every Zulip realm must have an owner, this command creates the
initial organization owner user for the new realm, using the same
workflow as `./manage.py create_user`.
"""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("realm_name", help="Name for the new organization")
        parser.add_argument(
            "--string-id",
            help="Subdomain for the new organization. Empty if root domain.",
            default="",
        )
        self.add_create_user_args(parser)

    def handle(self, *args: Any, **options: str) -> None:
        realm_name = options["realm_name"]
        string_id = options["string_id"]

        create_user_params = self.get_create_user_params(options)

        try:
            realm = do_create_realm(string_id=string_id, name=realm_name)
        except AssertionError as e:
            raise CommandError(str(e))

        do_create_user(
            create_user_params.email,
            create_user_params.password,
            realm,
            create_user_params.full_name,
            # Explicitly set tos_version=None. For servers that
            # have configured Terms of Service, this means that
            # users created via this mechanism will be prompted to
            # accept the Terms of Service on first login.
            role=UserProfile.ROLE_REALM_OWNER,
            realm_creation=True,
            tos_version=None,
            acting_user=None,
        )
