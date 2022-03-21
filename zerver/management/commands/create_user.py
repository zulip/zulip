import argparse
import logging
from typing import Any, Optional

from django.conf import settings
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
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        if "email" not in options:
            email = input("Email: ")
        else:
            email = options["email"]

        try:
            validators.validate_email(email)
        except ValidationError:
            raise CommandError("Invalid email address.")

        if "full_name" not in options:
            full_name = input("Full name: ")
        else:
            full_name = options["full_name"]

        if options["password_file"] is not None:
            with open(options["password_file"]) as f:
                pw: Optional[str] = f.read().strip()
        elif options["password"] is not None:
            logging.warning(
                "Passing password on the command line is insecure; prefer --password-file."
            )
            pw = options["password"]
        else:
            # initial_password will return a random password that
            # is a salted hash of the email address in a
            # development environment, and None in a production
            # environment.
            user_initial_password = initial_password(email)
            if user_initial_password is None:
                logging.info("User will be created with a disabled password.")
            else:
                assert settings.DEVELOPMENT
                logging.info("Password will be available via `./manage.py print_initial_password`.")
            pw = user_initial_password

        try:
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
