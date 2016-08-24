from __future__ import absolute_import

from typing import Any, Iterable, Tuple

from django.core.management.base import BaseCommand

from django.contrib.sites.models import Site
from zerver.models import UserProfile, Stream, Recipient, \
    Subscription, Realm, get_client, email_to_username
from django.conf import settings
from zerver.lib.bulk_create import bulk_create_users
from zerver.lib.actions import set_default_streams, do_create_realm

from optparse import make_option
from six import text_type

settings.TORNADO_SERVER = None

def create_users(name_list, bot_type=None):
    # type: (Iterable[Tuple[text_type, text_type]], int) -> None
    realms = {}
    for realm in Realm.objects.all():
        realms[realm.domain] = realm

    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    bulk_create_users(realms, user_set, bot_type)

class Command(BaseCommand):
    help = "Populate an initial database for Zulip Voyager"

    option_list = BaseCommand.option_list + (
        make_option('--extra-users',
                    dest='extra_users',
                    type='int',
                    default=0,
                    help='The number of extra users to create'),
        )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        Realm.objects.create(domain=settings.INTERNAL_BOT_DOMAIN)

        names = [(settings.FEEDBACK_BOT_NAME, settings.FEEDBACK_BOT)]
        create_users(names, bot_type=UserProfile.DEFAULT_BOT)

        get_client("website")
        get_client("API")

        internal_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                         for bot in settings.INTERNAL_BOTS]
        create_users(internal_bots, bot_type=UserProfile.DEFAULT_BOT)
        # Set the owners for these bots to the bots themselves
        bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in internal_bots])
        for bot in bots:
            bot.bot_owner = bot
            bot.save()

        # Initialize the email gateway bot as an API Super User
        email_gateway_bot = UserProfile.objects.get(email__iexact=settings.EMAIL_GATEWAY_BOT)
        email_gateway_bot.is_api_super_user = True
        email_gateway_bot.save()

        self.stdout.write("Successfully populated database with initial data.\n")
        self.stdout.write("Please run ./manage.py generate_realm_creation_link to generate link for creating organization")

    site = Site.objects.get_current()
    site.domain = settings.EXTERNAL_HOST
    site.save()
