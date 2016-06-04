from __future__ import absolute_import
from __future__ import print_function

from optparse import make_option

from typing import Any

from django.core.management.base import BaseCommand

from zerver.lib.actions import create_stream_if_needed, do_add_subscription
from zerver.models import UserProfile, get_realm, get_user_profile_by_email

class Command(BaseCommand):
    help = """Add some or all users in a realm to a set of streams."""

    option_list = BaseCommand.option_list + (
        make_option('-d', '--domain',
                    dest='domain',
                    type='str',
                    help='The name of the realm in which you are adding people to streams.'),
        make_option('-s', '--streams',
                    dest='streams',
                    type='str',
                    help='A comma-separated list of stream names.'),
        make_option('-u', '--users',
                    dest='users',
                    type='str',
                    help='A comma-separated list of email addresses.'),
        make_option('-a', '--all-users',
                    dest='all_users',
                    action="store_true",
                    default=False,
                    help='Add all users in this realm to these streams.'),
        )

    def handle(self, **options):
        # type: (**Any) -> None
        if options["domain"] is None or options["streams"] is None or \
                (options["users"] is None and options["all_users"] is None):
            self.print_help("python manage.py", "add_users_to_streams")
            exit(1)

        stream_names = set([stream.strip() for stream in options["streams"].split(",")])
        realm = get_realm(options["domain"])

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
                did_subscribe = do_add_subscription(user_profile, stream)
                print("%s %s to %s" % (
                    "Subscribed" if did_subscribe else "Already subscribed",
                    user_profile.email, stream_name))
