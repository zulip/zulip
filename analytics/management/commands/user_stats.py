from __future__ import absolute_import
from __future__ import print_function

import datetime
import pytz

from django.core.management.base import BaseCommand
from zerver.models import UserProfile, Realm, Stream, Message, get_realm
from six.moves import range

class Command(BaseCommand):
    help = "Generate statistics on user activity."

    def add_arguments(self, parser):
        parser.add_argument('realms', metavar='<realm>', type=str, nargs='*',
                            help="realm to generate statistics for")

    def messages_sent_by(self, user, week):
        start = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=(week + 1)*7)
        end = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=week*7)
        return Message.objects.filter(sender=user, pub_date__gt=start, pub_date__lte=end).count()

    def handle(self, *args, **options):
        if options['realms']:
            try:
                realms = [get_realm(domain) for domain in options['realms']]
            except Realm.DoesNotExist as e:
                print(e)
                exit(1)
        else:
            realms = Realm.objects.all()

        for realm in realms:
            print(realm.domain)
            user_profiles = UserProfile.objects.filter(realm=realm, is_active=True)
            print("%d users" % (len(user_profiles),))
            print("%d streams" % (len(Stream.objects.filter(realm=realm)),))

            for user_profile in user_profiles:
                print("%35s" % (user_profile.email,), end=' ')
                for week in range(10):
                    print("%5d" % (self.messages_sent_by(user_profile, week)), end=' ')
                print("")
