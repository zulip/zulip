import datetime
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.models import Message, Realm, Stream, UserProfile, get_realm

class Command(BaseCommand):
    help = "Generate statistics on user activity."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('realms', metavar='<realm>', type=str, nargs='*',
                            help="realm to generate statistics for")

    def messages_sent_by(self, user: UserProfile, week: int) -> int:
        start = timezone_now() - datetime.timedelta(days=(week + 1)*7)
        end = timezone_now() - datetime.timedelta(days=week*7)
        return Message.objects.filter(sender=user, pub_date__gt=start, pub_date__lte=end).count()

    def handle(self, *args: Any, **options: Any) -> None:
        if options['realms']:
            try:
                realms = [get_realm(string_id) for string_id in options['realms']]
            except Realm.DoesNotExist as e:
                print(e)
                exit(1)
        else:
            realms = Realm.objects.all()

        for realm in realms:
            print(realm.string_id)
            user_profiles = UserProfile.objects.filter(realm=realm, is_active=True)
            print("%d users" % (len(user_profiles),))
            print("%d streams" % (len(Stream.objects.filter(realm=realm)),))

            for user_profile in user_profiles:
                print("%35s" % (user_profile.email,), end=' ')
                for week in range(10):
                    print("%5d" % (self.messages_sent_by(user_profile, week)), end=' ')
                print("")
