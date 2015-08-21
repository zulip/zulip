from __future__ import absolute_import

from django.core.management.base import BaseCommand

from django.contrib.sites.models import Site
from zerver.models import UserProfile, Stream, Recipient, \
    Subscription, Realm, get_client, email_to_username
from django.conf import settings
from zerver.lib.bulk_create import bulk_create_users
from zerver.lib.actions import set_default_streams, do_create_realm

from optparse import make_option

settings.TORNADO_SERVER = None

def create_users(name_list, bot=False):
    realms = {}
    for realm in Realm.objects.all():
        realms[realm.domain] = realm

    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    bulk_create_users(realms, user_set, bot)

class Command(BaseCommand):
    help = "Populate an initial database for Zulip Voyager"

    option_list = BaseCommand.option_list + (
        make_option('--extra-users',
                    dest='extra_users',
                    type='int',
                    default=0,
                    help='The number of extra users to create'),
        )

    def handle(self, **options):
        Realm.objects.create(domain="zulip.com")

        names = [(settings.FEEDBACK_BOT_NAME, settings.FEEDBACK_BOT)]
        create_users(names, bot=True)

        get_client("website")
        get_client("API")

        internal_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                         for bot in settings.INTERNAL_BOTS]
        create_users(internal_bots, bot=True)
        # Set the owners for these bots to the bots themselves
        bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in internal_bots])
        for bot in bots:
            bot.bot_owner = bot
            bot.save()

        (admin_realm, _) = do_create_realm(settings.ADMIN_DOMAIN,
                                           settings.ADMIN_DOMAIN, True)

        set_default_streams(admin_realm, ["social", "engineering"])

        self.stdout.write("Successfully populated database with initial data.\n")

    site = Site.objects.get_current()
    site.domain = settings.EXTERNAL_HOST
    site.save()
