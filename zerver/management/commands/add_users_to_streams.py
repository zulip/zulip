from __future__ import absolute_import
from __future__ import print_function

from optparse import make_option

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.actions import create_stream_if_needed, bulk_add_subscriptions
from zerver.models import UserProfile, get_realm_by_string_id, get_user_profile_by_email

class Command(BaseCommand):
    help = """Add some or all users in a realm to a set of streams."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument(
            '-r', '--realm',
            dest='string_id',
            type=str,
            help='The name of the realm in which you are adding people to streams.')

        parser.add_argument(
            '-s', '--streams',
            dest='streams',
            type=str,
            help='A comma-separated list of stream names.')

        parser.add_argument(
            '-u', '--users',
            dest='users',
            type=str,
            help='A comma-separated list of email addresses.')

        parser.add_argument(
            '-a', '--all-users',
            dest='all_users',
            action="store_true",
            default=False,
            help='Add all users in this realm to these streams.')

    def handle(self, **options):
        # type: (**Any) -> None
        if options["string_id"] is None or options["streams"] is None or \
                (options["users"] is None and options["all_users"] is None):
            self.print_help("./manage.py", "add_users_to_streams")
            exit(1)

        stream_names = set([stream.strip() for stream in options["streams"].split(",")])
        realm = get_realm_by_string_id(options["string_id"])

        if options["all_users"]:
            user_profiles = UserProfile.objects.filter(realm=realm)
        else:
            emails = set([email.strip() for email in options["users"].split(",")])
            user_profiles = []
            for email in emails:
                user_profiles.append(get_user_profile_by_email(email))

        for stream_name in set(stream_names):
            for user_profile in user_profiles:
                stream, _ = create_stream_if_needed(user_profile.realm, stream_name)
                _ignore, already_subscribed = bulk_add_subscriptions([stream], [user_profile])
                was_there_already = user_profile.id in {tup[0].id for tup in already_subscribed}
                print("%s %s to %s" % (
                    "Already subscribed" if was_there_already else "Subscribed",
                    user_profile.email, stream_name))
