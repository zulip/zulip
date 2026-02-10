import getpass
from argparse import ArgumentParser
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    # This is our version of the original Django changepassword command adjusted
    # to be able to find UserProfiles by email+realm.
    # We change the arguments the command takes to fit our
    # model of username+realm and change accordingly the
    # logic inside the handle method which fetches the user
    # from the database. The rest of the logic remains unchanged.

    help = "Change a user's password."
    requires_migrations_checks = True
    requires_system_checks: list[str] = []

    def _get_pass(self, prompt: str = "Password: ") -> str:
        p = getpass.getpass(prompt=prompt)
        if not p:
            raise CommandError("aborted")
        return p

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("email", metavar="<email>", help="email of user to change role")
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: Any) -> str:
        email = options["email"]
        realm = self.get_realm(options)

        u = self.get_user(email, realm)

        # Code below is taken from the Django version of this command:
        self.stdout.write(f"Changing password for user '{u}'")

        MAX_TRIES = 3
        count = 0
        p1, p2 = "1", "2"  # To make them initially mismatch.
        password_validated = False
        while (p1 != p2 or not password_validated) and count < MAX_TRIES:
            p1 = self._get_pass()
            p2 = self._get_pass("Password (again): ")
            if p1 != p2:
                self.stdout.write("Passwords do not match. Please try again.")
                count += 1
                # Don't validate passwords that don't match.
                continue
            try:
                validate_password(p2, u)
            except ValidationError as err:
                self.stderr.write("\n".join(err.messages))
                count += 1
            else:
                password_validated = True

        if count == MAX_TRIES:
            raise CommandError(f"Aborting password change for user '{u}' after {count} attempts")

        u.set_password(p1)
        u.save()

        return f"Password changed successfully for user '{u}'"
