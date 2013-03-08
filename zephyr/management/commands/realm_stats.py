import datetime
import pytz

from django.core.management.base import BaseCommand
from zephyr.models import UserProfile, Realm, Stream, Message, Recipient, StreamColor

class Command(BaseCommand):
    help = "Generate statistics on realm activity."

    def messages_sent_by(self, user, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return Message.objects.filter(sender=user, pub_date__gt=sent_time_cutoff).count()

    def stream_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return Message.objects.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff,
                                      recipient__type=Recipient.STREAM).count()

    def private_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return Message.objects.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff).exclude(
            recipient__type=Recipient.STREAM).exclude(recipient__type=Recipient.HUDDLE).count()

    def group_private_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return Message.objects.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff).exclude(
            recipient__type=Recipient.STREAM).exclude(recipient__type=Recipient.PERSONAL).count()

    def handle(self, *args, **options):
        if args:
            try:
                realms = [Realm.objects.get(domain=domain) for domain in args]
            except Realm.DoesNotExist, e:
                print e
                exit(1)
        else:
            realms = Realm.objects.all()

        for realm in realms:
            print realm.domain
            user_profiles = UserProfile.objects.filter(realm=realm)
            print "%d users" % (len(user_profiles),)
            print "%d streams" % (Stream.objects.filter(realm=realm).count(),)

            for days_ago in (1, 7, 30):
                print "In last %d days, users sent:" % (days_ago,)
                sender_quantities = [self.messages_sent_by(user, days_ago) for user in user_profiles]
                for quantity in sorted(sender_quantities, reverse=True):
                    print quantity,
                print ""

                print "%d stream messages" % (self.stream_messages(realm, days_ago),)
                print "%d one-on-one private messages" % (self.private_messages(realm, days_ago),)
                print "%d group private messages" % (self.group_private_messages(realm, days_ago),)
            print "%.2f%% have desktop notifications enabled" % (float(len(user_profiles.filter(
                            enable_desktop_notifications=True))) * 100 /len(user_profiles),)
            colorizers = 0
            for profile in user_profiles:
                if StreamColor.objects.filter(subscription__user_profile=profile).count() > 0:
                    colorizers += 1
            print "%.2f%% have colorized streams" % (float(colorizers) * 100/len(user_profiles),)

            print "%.2f%% have Enter sends" % (
                float(len(filter(lambda x: x.enter_sends, user_profiles))) * 100 / len(user_profiles),)

            all_message_count = Message.objects.filter(sender__realm=realm).count()
            multi_paragraph_message_count = Message.objects.filter(sender__realm=realm,
                                                                   content__contains="\n\n").count()
            print "%.2f%% of all messages are multi-paragraph" % (
                float(multi_paragraph_message_count) * 100 / all_message_count)
            print ""
