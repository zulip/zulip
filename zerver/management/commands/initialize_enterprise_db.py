from __future__ import absolute_import

from django.core.management.base import BaseCommand

from django.contrib.sites.models import Site
from zerver.models import UserProfile, Stream, Recipient, \
    Subscription, Realm, get_client, email_to_username
from django.conf import settings
from zerver.lib.bulk_create import bulk_create_streams, bulk_create_users

from optparse import make_option

settings.TORNADO_SERVER = None

def create_users(realms, name_list, bot=False):
    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    bulk_create_users(realms, user_set, bot)

def create_streams(realms, realm, stream_list):
    stream_set = set()
    for stream_name in stream_list:
        stream_set.add((realm.domain, stream_name))
    bulk_create_streams(realms, stream_set)

class Command(BaseCommand):
    help = "Populate a local server database"

    option_list = BaseCommand.option_list + (
        make_option('--extra-users',
                    dest='extra_users',
                    type='int',
                    default=0,
                    help='The number of extra users to create'),
        )

    def handle(self, **options):
        zulip_realm = Realm.objects.create(domain="zulip.com")
        Realm.objects.create(domain=settings.ADMIN_DOMAIN)
        realms = {}
        for realm in Realm.objects.all():
            realms[realm.domain] = realm

        # Create test Users (UserProfiles are automatically created,
        # as are subscriptions to the ability to receive personals).
        names = [("Othello, the Moor of Venice", "othello@zulip.com"), ("Iago", "iago@zulip.com"),
                 ("Prospero from The Tempest", "prospero@zulip.com"),
                 ("Cordelia Lear", "cordelia@zulip.com"), ("King Hamlet", "hamlet@zulip.com")]
        for i in xrange(options["extra_users"]):
            names.append(('Extra User %d' % (i,), 'extrauser%d@zulip.com' % (i,)))
        create_users(realms, names)
        # Create public streams.
        stream_list = ["Verona", "Denmark", "Scotland", "Venice", "Rome"]
        create_streams(realms, zulip_realm, stream_list)
        recipient_streams = [Stream.objects.get(name=name, realm=zulip_realm).id for name in stream_list]

        # Create subscriptions to streams
        # TODO: Replace this with something nonrandom
        subscriptions_to_add = []
        profiles = UserProfile.objects.select_related().all()
        for i, profile in enumerate(profiles):
            # Subscribe to some streams.
            for type_id in recipient_streams[:int(len(recipient_streams) *
                                                  float(i)/len(profiles)) + 1]:
                r = Recipient.objects.get(type=Recipient.STREAM, type_id=type_id)
                s = Subscription(recipient=r, user_profile=profile)
                subscriptions_to_add.append(s)
        Subscription.objects.bulk_create(subscriptions_to_add)

        # Create the "website" and "API" clients; if we don't, the
        # default values in zerver/decorators.py will not work
        # with the Django test suite.
        get_client("website")
        get_client("API")

        all_realm_bots = [(bot['name'], bot['email_template'] % (settings.ADMIN_DOMAIN,)) for bot in settings.REALM_BOTS]
        create_users(realms, all_realm_bots, bot=True)
        # Set the owners for these bots to the bots themselves
        bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in all_realm_bots])
        for bot in bots:
            bot.bot_owner = bot
            bot.save()

        self.stdout.write("Successfully populated database with initial data.\n")

    site = Site.objects.get_current()
    site.domain = 'zulip.com'
    site.save()
