from django.core.management.base import BaseCommand
from zephyr.models import UserProfile, Subscription, Recipient, Message, Stream
from django.db.models import Q

import datetime
import pytz
from optparse import make_option

class Command(BaseCommand):
    help = """Delete all inactive tutorial stream subscriptions."""

    option_list = BaseCommand.option_list + (
        make_option('-f', '--for-real',
                    dest='for_real',
                    action='store_true',
                    default=False,
                    help="Actually deactive subscriptions. Default is a dry run."),
        )

    def has_sent_to(self, user_profile, recipient):
        return Message.objects.filter(sender=user_profile, recipient=recipient).count() != 0

    def handle(self, **options):
        possible_tutorial_streams = Stream.objects.filter(Q(name__startswith='tutorial-'))

        tutorial_bot = UserProfile.objects.get(user__email="humbug+tutorial@humbughq.com")

        for stream in possible_tutorial_streams:
            recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)
            subscribers = Subscription.objects.filter(recipient=recipient, active=True)
            if ((subscribers.count() == 1) and self.has_sent_to(tutorial_bot, recipient)):
                # This is a tutorial stream.
                most_recent_message = Message.objects.filter(
                    recipient=recipient).latest("pub_date")
                # This cutoff must be more generous than the tutorial bot cutoff
                # in the client code.
                cutoff = datetime.datetime.now(tz=pytz.utc) - datetime.timedelta(hours=2)

                if most_recent_message.pub_date < cutoff:
                    # The tutorial has expired, so delete the stream.
                    print stream.name, most_recent_message.pub_date
                    if options["for_real"]:
                        tutorial_user = subscribers[0]
                        tutorial_user.active = False
                        tutorial_user.save()

        if options["for_real"]:
            print "Subscriptions deactivated."
        else:
            print "This was a dry run. Pass -f to actually deactivate."
