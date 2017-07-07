# Library code for use in management commands
from __future__ import absolute_import
from __future__ import print_function

from argparse import ArgumentParser
from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand, CommandError
from typing import Any, Dict, Optional, Text

from zerver.models import Realm, UserProfile

def is_integer_string(val):
    # type: (str) -> bool
    try:
        int(val)
        return True
    except ValueError:
        return False

class ZulipBaseCommand(BaseCommand):
    def add_realm_args(self, parser, required=False):
        # type: (ArgumentParser, bool) -> None
        parser.add_argument(
            '-r', '--realm',
            dest='realm_id',
            required=required,
            type=str,
            help='The numeric or string ID (subdomain) of the Zulip organization to modify.')

    def get_realm(self, options):
        # type: (Dict[str, Any]) -> Optional[Realm]
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
            raise CommandError("The is no realm with id '%s'. Aborting." %
                               (options["realm_id"],))

    def get_user(self, email, realm):
        # type: (Text, Optional[Realm]) -> UserProfile

        # If a realm is specified, try to find the user there, and
        # throw an error if they don't exist.
        if realm is not None:
            try:
                return UserProfile.objects.select_related().get(email__iexact=email.strip(), realm=realm)
            except UserProfile.DoesNotExist:
                raise CommandError("The realm '%s' does not contain a user with email '%s'" % (realm, email))

        # Realm is None in the remaining code path.  Here, we
        # optimistically try to see if there is exactly one user with
        # that email; if so, we'll return it.
        try:
            return UserProfile.objects.select_related().get(email__iexact=email.strip())
        except MultipleObjectsReturned:
            raise CommandError("This Zulip server contains multiple users with that email " +
                               "(in different realms); please pass `--realm` to specify which one to modify.")
        except UserProfile.DoesNotExist:
            raise CommandError("This Zulip server does not contain a user with email '%s'" % (email,))
