from __future__ import absolute_import

import datetime
import pytz

from django.core.management.base import BaseCommand
from django.db.models import Count
from zerver.models import UserProfile, Realm, Stream, Message, Recipient, UserActivity, \
    Subscription, UserMessage

MOBILE_CLIENT_LIST = ["Android", "ios"]
HUMAN_CLIENT_LIST = MOBILE_CLIENT_LIST + ["website"]

human_messages = Message.objects.filter(sending_client__name__in=HUMAN_CLIENT_LIST)

class Command(BaseCommand):
    help = "Generate statistics on realm activity."

    def add_arguments(self, parser):
        parser.add_argument('realms', metavar='<realm>', type=str, nargs='*',
                            help="realm to generate statistics for")

    def active_users(self, realm):
        # Has been active (on the website, for now) in the last 7 days.
        activity_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=7)
        return [activity.user_profile for activity in \
                    UserActivity.objects.filter(user_profile__realm=realm,
                                                user_profile__is_active=True,
                                                last_visit__gt=activity_cutoff,
                                                query="/json/update_pointer",
                                                client__name="website")]

    def messages_sent_by(self, user, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return human_messages.filter(sender=user, pub_date__gt=sent_time_cutoff).count()

    def total_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return Message.objects.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff).count()

    def human_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return human_messages.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff).count()

    def api_messages(self, realm, days_ago):
        return (self.total_messages(realm, days_ago) - self.human_messages(realm, days_ago))

    def stream_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return human_messages.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff,
                                     recipient__type=Recipient.STREAM).count()

    def private_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return human_messages.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff).exclude(
            recipient__type=Recipient.STREAM).exclude(recipient__type=Recipient.HUDDLE).count()

    def group_private_messages(self, realm, days_ago):
        sent_time_cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(days=days_ago)
        return human_messages.filter(sender__realm=realm, pub_date__gt=sent_time_cutoff).exclude(
            recipient__type=Recipient.STREAM).exclude(recipient__type=Recipient.PERSONAL).count()

    def report_percentage(self, numerator, denominator, text):
        if not denominator:
            fraction = 0.0
        else:
            fraction = numerator / float(denominator)
        print "%.2f%% of" % (fraction * 100,), text

    def handle(self, *args, **options):
        if options['realms']:
            try:
                realms = [Realm.objects.get(domain=domain) for domain in options['realms']]
            except Realm.DoesNotExist, e:
                print e
                exit(1)
        else:
            realms = Realm.objects.all()

        for realm in realms:
            print realm.domain

            user_profiles = UserProfile.objects.filter(realm=realm, is_active=True)
            active_users = self.active_users(realm)
            num_active = len(active_users)

            print "%d active users (%d total)" % (num_active, len(user_profiles))
            streams = Stream.objects.filter(realm=realm).extra(
                tables=['zerver_subscription', 'zerver_recipient'],
                where=['zerver_subscription.recipient_id = zerver_recipient.id',
                       'zerver_recipient.type = 2',
                       'zerver_recipient.type_id = zerver_stream.id',
                       'zerver_subscription.active = true']).annotate(count=Count("name"))
            print "%d streams" % (streams.count(),)

            for days_ago in (1, 7, 30):
                print "In last %d days, users sent:" % (days_ago,)
                sender_quantities = [self.messages_sent_by(user, days_ago) for user in user_profiles]
                for quantity in sorted(sender_quantities, reverse=True):
                    print quantity,
                print ""

                print "%d stream messages" % (self.stream_messages(realm, days_ago),)
                print "%d one-on-one private messages" % (self.private_messages(realm, days_ago),)
                print "%d messages sent via the API" % (self.api_messages(realm, days_ago),)
                print "%d group private messages" % (self.group_private_messages(realm, days_ago),)

            num_notifications_enabled = len(filter(lambda x: x.enable_desktop_notifications == True,
                                                   active_users))
            self.report_percentage(num_notifications_enabled, num_active,
                                   "active users have desktop notifications enabled")

            num_enter_sends = len(filter(lambda x: x.enter_sends, active_users))
            self.report_percentage(num_enter_sends, num_active,
                                   "active users have enter-sends")

            all_message_count = human_messages.filter(sender__realm=realm).count()
            multi_paragraph_message_count = human_messages.filter(
                sender__realm=realm, content__contains="\n\n").count()
            self.report_percentage(multi_paragraph_message_count, all_message_count,
                                   "all messages are multi-paragraph")

            # Starred messages
            starrers = UserMessage.objects.filter(user_profile__in=user_profiles,
                                                  flags=UserMessage.flags.starred).values(
                "user_profile").annotate(count=Count("user_profile"))
            print "%d users have starred %d messages" % (
                len(starrers), sum([elt["count"] for elt in starrers]))

            active_user_subs = Subscription.objects.filter(
                user_profile__in=user_profiles, active=True)

            # Streams not in home view
            non_home_view = active_user_subs.filter(in_home_view=False).values(
                "user_profile").annotate(count=Count("user_profile"))
            print "%d users have %d streams not in home view" % (
                len(non_home_view), sum([elt["count"] for elt in non_home_view]))

            # Code block markup
            markup_messages = human_messages.filter(
                sender__realm=realm, content__contains="~~~").values(
                "sender").annotate(count=Count("sender"))
            print "%d users have used code block markup on %s messages" % (
                len(markup_messages), sum([elt["count"] for elt in markup_messages]))

            # Notifications for stream messages
            notifications = active_user_subs.filter(notifications=True).values(
                "user_profile").annotate(count=Count("user_profile"))
            print "%d users receive desktop notifications for %d streams" % (
                len(notifications), sum([elt["count"] for elt in notifications]))

            print ""
