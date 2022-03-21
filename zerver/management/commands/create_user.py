import argparse
import sys
from typing import Any

from django.core import validators
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db.utils import IntegrityError

from zerver.lib.actions import do_create_user
from zerver.lib.initial_password import initial_password
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
        if not options["tos"]:
            raise CommandError(
                """You must confirm that this user has accepted the
Terms of Service by passing --this-user-has-accepted-the-tos."""
            )
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        try:
            email = options["email"]
            full_name = options["full_name"]
            try:
                validators.validate_email(email)
            except ValidationError:
                raise CommandError("Invalid email address.")
        except KeyError:
            if "email" in options or "full_name" in options:
                raise CommandError(
                    """Either specify an email and full name as two
parameters, or specify no parameters for interactive user creation."""
                )
            else:
                while True:
                    email = input("Email: ")
                    try:
                        validators.validate_email(email)
                        break
                    except ValidationError:
                        print("Invalid email address.", file=sys.stderr)
                full_name = input("Full name: ")

        try:
            if options["password_file"] is not None:
                with open(options["password_file"]) as f:
                    pw = f.read().strip()
            elif options["password"] is not None:
                pw = options["password"]
            else:
                user_initial_password = initial_password(email)
                if user_initial_password is None:
                    raise CommandError("Password is unusable.")
                pw = user_initial_password
            do_create_user(
                email,
                pw,
                realm,
                full_name,
                # Explicitly set tos_version=None. For servers that
                # have configured Terms of Service, this means that
                # users created via this mechanism will be prompted to
                # accept the Terms of Service on first login.
                tos_version=None,
                acting_user=None,
            )
        except IntegrityError:
            raise CommandError("User already exists.")
