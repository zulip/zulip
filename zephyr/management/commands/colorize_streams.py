from optparse import make_option

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from zephyr.models import Realm, Stream, UserProfile, Subscription, \
    Message, Recipient

class Command(BaseCommand):
    help = """Colorize streams in a realm for people who have not already colored their streams."""

    option_list = BaseCommand.option_list + (
        make_option('-d', '--domain',
                    dest='domain',
                    type='str',
                    help='The name of the realm in which you are colorizing streams.'),
        )

    def handle(self, **options):
        if options["domain"] is None:
            self.print_help("python manage.py", "colorize_streams")
            exit(1)

        realm = Realm.objects.get(domain=options["domain"])
        user_profiles = UserProfile.objects.filter(realm=realm)
        users_who_need_colors = filter(lambda profile: Subscription.objects.filter(
                user_profile=profile).filter(~Q(color=Subscription.DEFAULT_STREAM_COLOR)).count() == 0, user_profiles)

        # Hand-selected colors from the current swatch options,
        # providing reasonable contrast for 1 - 7 streams.
        colors = [
            "#76ce90", # light forest green
            "#f5ce6e", # goldenrod
            "#a6c7e5", # light blue
            "#b0a5fd", # volet
            "#e79ab5", # pink
            "#bfd56f", # greenish-yellow
            "#f4ae55", # orange
            ]

        print "Setting stream colors for:"
        for user_profile in users_who_need_colors:
            print "    ", user_profile.full_name

        stream_ids = [result['recipient__type_id'] for result in \
                          Message.objects.filter(sender__realm=realm,
                                                 recipient__type=Recipient.STREAM)
                      .values('recipient__type_id').annotate(
                count=Count('recipient__type_id')).order_by('-count')]

        print "Setting color for:"
        for stream_id, color in zip(stream_ids, colors):
            # Give everyone the same color for a stream.
            print "    ", Stream.objects.get(id=stream_id).name
            # If this realm has more streams than preselected colors,
            # only color the N most popular.
            recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream_id)
            for user_profile in users_who_need_colors:
                try:
                    subscription = Subscription.objects.get(user_profile=user_profile,
                                                            recipient=recipient)
                except Subscription.DoesNotExist:
                    # Not subscribed
                    continue

                subscription.color = color
                subscription.save(update_fields=["color"])
