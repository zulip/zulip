import argparse
from typing import Any

from django.core import validators
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db.utils import IntegrityError

from zerver.lib.actions import do_create_realm, do_create_user
from zerver.lib.initial_password import initial_password
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """Create a new REALM with its owner."""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", metavar="<name>", help="name of REALM")
        parser.add_argument("--string-id", help="The REALM string-id. Empty if not used.")
        parser.add_argument(
            "--password",
            help="password of new user. For development only."
            " Note that we recommend against setting "
            "passwords this way, since they can be snooped by any user account "
            "on the server via `ps -ef` or by any superuser with"
            "read access to the user's bash history.",
        )
        parser.add_argument(
            "--password-file", help="The file containing the password of the new user."
        )
        parser.add_argument(
            "--disable-invite-required",
            action="store_true",
            help="Create Realm with invite disabled.",
        )
        parser.add_argument(
            "email",
            metavar="<email>",
            help="email address of the REALM admin",
        )
        parser.add_argument(
            "full_name",
            metavar="<full name>",
            help="full name of the REALM user",
        )

    def handle(self, *args: Any, **options: str) -> None:
        name = options["name"]
        email = options["email"]
        full_name = options["full_name"]
        try:
            validators.validate_email(email)
        except ValidationError:
            raise CommandError("Invalid email address.")

        if "string_id" in options and options["string_id"] is not None:
            string_id = options["string_id"]
        else:
            string_id = ""

        if "password_file" in options and options["password_file"] is not None:
            with open(options["password_file"]) as f:
                pw = f.read().strip()
        elif "password" in options and options["password"] is not None:
            pw = options["password"]
        else:
            user_initial_password = initial_password(email)
            if user_initial_password is None:
                raise CommandError("Password is unusable.")
            pw = user_initial_password
        if "disable_invite_required" in options and options["disable_invite_required"] is not None:
            invite_required = False
        else:
            invite_required = True

        try:
            realm = do_create_realm(string_id=string_id, name=name, invite_required=invite_required)
        except AssertionError:
            raise CommandError("Realm '{}' already exists.".format(string_id))

        try:
            do_create_user(
                email,
                pw,
                realm,
                full_name,
                role=UserProfile.ROLE_REALM_OWNER,
                acting_user=None,
            )
        except IntegrityError:
            raise CommandError("User already exists.")
