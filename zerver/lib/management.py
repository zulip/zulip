# Library code for use in management commands
import logging
from argparse import ArgumentParser, RawTextHelpFormatter
from dataclasses import dataclass
from typing import Any, Collection, Dict, Optional

from django.conf import settings
from django.core import validators
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.lib.initial_password import initial_password
from zerver.models import Client, Realm, UserProfile, get_client


def is_integer_string(val: str) -> bool:
    try:
        int(val)
        return True
    except ValueError:
        return False


def check_config() -> None:
    for setting_name, default in settings.REQUIRED_SETTINGS:
        # if required setting is the same as default OR is not found in settings,
        # throw error to add/set that setting in config
        try:
            if getattr(settings, setting_name) != default:
                continue
        except AttributeError:
            pass

        raise CommandError(f"Error: You must set {setting_name} in /etc/zulip/settings.py.")


@dataclass
class CreateUserParameters:
    email: str
    full_name: str
    password: Optional[str]


class ZulipBaseCommand(BaseCommand):
    # Fix support for multi-line usage
    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_realm_args(
        self, parser: ArgumentParser, *, required: bool = False, help: Optional[str] = None
    ) -> None:
        if help is None:
            help = """The numeric or string ID (subdomain) of the Zulip organization to modify.
You can use the command list_realms to find ID of the realms in this server."""

        parser.add_argument("-r", "--realm", dest="realm_id", required=required, help=help)

    def add_create_user_args(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "email",
            metavar="<email>",
            nargs="?",
            help="Email address for the new user",
        )
        parser.add_argument(
            "full_name",
            metavar="<full name>",
            nargs="?",
            help="Full name for the new user",
        )
        parser.add_argument(
            "--password",
            help="""\
Password for the new user. Recommended only in a development environment.

Sending passwords via command-line arguments is insecure,
since it can be snooped by any process running on the
server via `ps -ef` or reading bash history. Prefer
--password-file.""",
        )
        parser.add_argument("--password-file", help="File containing a password for the new user.")

    def add_user_list_args(
        self,
        parser: ArgumentParser,
        help: str = "A comma-separated list of email addresses.",
        all_users_help: str = "All users in realm.",
    ) -> None:
        parser.add_argument("-u", "--users", help=help)

        parser.add_argument("-a", "--all-users", action="store_true", help=all_users_help)

    def get_realm(self, options: Dict[str, Any]) -> Optional[Realm]:
        val = options["realm_id"]
        if val is None:
            return None

        # If they specified a realm argument, we need to ensure the
        # realm exists.  We allow two formats: the numeric ID for the
        # realm and the string ID of the realm.
        try:
            if is_integer_string(val):
                return Realm.objects.get(id=val)
            return Realm.objects.get(string_id=val)
        except Realm.DoesNotExist:
            raise CommandError(
                "There is no realm with id '{}'. Aborting.".format(options["realm_id"])
            )

    def get_users(
        self,
        options: Dict[str, Any],
        realm: Optional[Realm],
        is_bot: Optional[bool] = None,
        include_deactivated: bool = False,
    ) -> Collection[UserProfile]:
        if "all_users" in options:
            all_users = options["all_users"]

            if not options["users"] and not all_users:
                raise CommandError("You have to pass either -u/--users or -a/--all-users.")

            if options["users"] and all_users:
                raise CommandError("You can't use both -u/--users and -a/--all-users.")

            if all_users and realm is None:
                raise CommandError("The --all-users option requires a realm; please pass --realm.")

            if all_users:
                user_profiles = UserProfile.objects.filter(realm=realm)
                if not include_deactivated:
                    user_profiles = user_profiles.filter(is_active=True)
                if is_bot is not None:
                    return user_profiles.filter(is_bot=is_bot)
                return user_profiles

        if options["users"] is None:
            return []
        emails = {email.strip() for email in options["users"].split(",")}
        return [self.get_user(email, realm) for email in emails]

    def get_user(self, email: str, realm: Optional[Realm]) -> UserProfile:
        # If a realm is specified, try to find the user there, and
        # throw an error if they don't exist.
        if realm is not None:
            try:
                return UserProfile.objects.select_related().get(
                    delivery_email__iexact=email.strip(), realm=realm
                )
            except UserProfile.DoesNotExist:
                raise CommandError(
                    f"The realm '{realm}' does not contain a user with email '{email}'"
                )

        # Realm is None in the remaining code path.  Here, we
        # optimistically try to see if there is exactly one user with
        # that email; if so, we'll return it.
        try:
            return UserProfile.objects.select_related().get(delivery_email__iexact=email.strip())
        except MultipleObjectsReturned:
            raise CommandError(
                "This Zulip server contains multiple users with that email "
                + "(in different realms); please pass `--realm` "
                "to specify which one to modify."
            )
        except UserProfile.DoesNotExist:
            raise CommandError(f"This Zulip server does not contain a user with email '{email}'")

    def get_client(self) -> Client:
        """Returns a Zulip Client object to be used for things done in management commands"""
        return get_client("ZulipServer")

    def get_create_user_params(self, options: Dict[str, Any]) -> CreateUserParameters:  # nocoverage
        """
        Parses parameters for user creation defined in add_create_user_args.
        """
        if options["email"] is None:
            email = input("Email: ")
        else:
            email = options["email"]

        try:
            validators.validate_email(email)
        except ValidationError:
            raise CommandError("Invalid email address.")

        if options["full_name"] is None:
            full_name = input("Full name: ")
        else:
            full_name = options["full_name"]

        if options["password_file"] is not None:
            with open(options["password_file"]) as f:
                password: Optional[str] = f.read().strip()
        elif options["password"] is not None:
            logging.warning(
                "Passing password on the command line is insecure; prefer --password-file."
            )
            password = options["password"]
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
            password = user_initial_password

        return CreateUserParameters(
            email=email,
            full_name=full_name,
            password=password,
        )
