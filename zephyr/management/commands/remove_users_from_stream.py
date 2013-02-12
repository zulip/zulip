from optparse import make_option

from django.core.management.base import BaseCommand

from zephyr.lib.actions import do_remove_subscription
from zephyr.models import Realm, User, UserProfile, get_stream

class Command(BaseCommand):
    help = """Remove some or all users in a realm from a stream."""

    option_list = BaseCommand.option_list + (
        make_option('-d', '--domain',
                    dest='domain',
                    type='str',
                    help='The name of the realm in which you are removing people.'),
        make_option('-s', '--stream',
                    dest='stream',
                    type='str',
                    help='A stream name.'),
        make_option('-u', '--users',
                    dest='users',
                    type='str',
                    help='A comma-separated list of email addresses.'),
        make_option('-a', '--all-users',
                    dest='all_users',
                    action="store_true",
                    default=False,
                    help='Remove all users in this realm from this stream.'),
        )

    def handle(self, **options):
        if options["domain"] is None or options["stream"] is None or \
                (options["users"] is None and options["all_users"] is None):
            self.print_help("python manage.py", "remove_users_from_stream")
            exit(1)

        realm = Realm.objects.get(domain=options["domain"])
        stream_name = options["stream"].strip()
        stream = get_stream(stream_name, realm)

        if options["all_users"]:
            user_profiles = UserProfile.objects.filter(realm=realm)
        else:
            emails = set([email.strip() for email in options["users"].split(",")])
            user_profiles = []
            for email in emails:
                user_profiles.append(UserProfile.objects.get(
                        user=User.objects.get(email__iexact=email)))

        for user_profile in user_profiles:
            did_remove = do_remove_subscription(user_profile, stream)
            print "%s %s from %s" % (
                "Removed" if did_remove else "Couldn't remove",
                user_profile.user.email, stream_name)
