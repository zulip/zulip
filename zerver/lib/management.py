# Library code for use in management commands

import time

from argparse import ArgumentParser, RawTextHelpFormatter

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand, CommandError
from typing import Any, Dict, Optional, List

from zerver.models import Realm, UserProfile, Client, get_client

def is_integer_string(val: str) -> bool:
    try:
        int(val)
        return True
    except ValueError:
        return False

def check_config() -> None:
    for (setting_name, default) in settings.REQUIRED_SETTINGS:
        # if required setting is the same as default OR is not found in settings,
        # throw error to add/set that setting in config
        try:
            if settings.__getattr__(setting_name) != default:
                continue
        except AttributeError:
            pass

        raise CommandError("Error: You must set %s in /etc/zulip/settings.py." % (setting_name,))

def sleep_forever() -> None:
    while True:  # nocoverage
        time.sleep(10**9)

class ZulipBaseCommand(BaseCommand):

    # Fix support for multi-line usage
    def create_parser(self, *args: Any, **kwargs: Any) -> ArgumentParser:
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_realm_args(self, parser: ArgumentParser, required: bool=False,
                       help: Optional[str]=None) -> None:
        if help is None:
            help = """The numeric or string ID (subdomain) of the Zulip organization to modify.
You can use the command list_realms to find ID of the realms in this server."""

        parser.add_argument(
            '-r', '--realm',
            dest='realm_id',
            required=required,
            type=str,
            help=help)

    def add_user_list_args(self, parser: ArgumentParser,
                           help: str='A comma-separated list of email addresses.',
                           all_users_help: str="All users in realm.") -> None:
        parser.add_argument(
            '-u', '--users',
            dest='users',
            type=str,
            help=help)

        parser.add_argument(
            '-a', '--all-users',
            dest='all_users',
            action="store_true",
            default=False,
            help=all_users_help)

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
            raise CommandError("There is no realm with id '%s'. Aborting." %
                               (options["realm_id"],))

    def get_users(self, options: Dict[str, Any], realm: Optional[Realm],
                  is_bot: Optional[bool]=None) -> List[UserProfile]:
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
                if is_bot is not None:
                    return user_profiles.filter(is_bot=is_bot)
                return user_profiles

        if options["users"] is None:
            return []
        emails = set([email.strip() for email in options["users"].split(",")])
        user_profiles = []
        for email in emails:
            user_profiles.append(self.get_user(email, realm))
        return user_profiles

    def get_user(self, email: str, realm: Optional[Realm]) -> UserProfile:

        # If a realm is specified, try to find the user there, and
        # throw an error if they don't exist.
        if realm is not None:
            try:
                return UserProfile.objects.select_related().get(
                    delivery_email__iexact=email.strip(), realm=realm)
            except UserProfile.DoesNotExist:
                raise CommandError("The realm '%s' does not contain a user with email '%s'" % (realm, email))

        # Realm is None in the remaining code path.  Here, we
        # optimistically try to see if there is exactly one user with
        # that email; if so, we'll return it.
        try:
            return UserProfile.objects.select_related().get(delivery_email__iexact=email.strip())
        except MultipleObjectsReturned:
            raise CommandError("This Zulip server contains multiple users with that email " +
                               "(in different realms); please pass `--realm` "
                               "to specify which one to modify.")
        except UserProfile.DoesNotExist:
            raise CommandError("This Zulip server does not contain a user with email '%s'" % (email,))

    def get_client(self) -> Client:
        """Returns a Zulip Client object to be used for things done in management commands"""
        return get_client("ZulipServer")
