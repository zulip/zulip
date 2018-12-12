
from argparse import ArgumentParser
from typing import Any, Iterable, Tuple, Optional

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.bulk_create import bulk_create_users
from zerver.models import Realm, UserProfile, \
    email_to_username, get_client, get_system_bot

settings.TORNADO_SERVER = None

def create_users(realm: Realm, name_list: Iterable[Tuple[str, str]], bot_type: Optional[int]=None) -> None:
    user_set = set()
    for full_name, email in name_list:
        short_name = email_to_username(email)
        user_set.add((email, full_name, short_name, True))
    bulk_create_users(realm, user_set, bot_type)

class Command(BaseCommand):
    help = "Populate an initial database for Zulip Voyager"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--extra-users',
                            dest='extra_users',
                            type=int,
                            default=0,
                            help='The number of extra users to create')

    def handle(self, *args: Any, **options: Any) -> None:
        if Realm.objects.count() > 0:
            print("Database already initialized; doing nothing.")
            return
        realm = Realm.objects.create(string_id=settings.INTERNAL_BOT_DOMAIN.split('.')[0])

        names = [(settings.FEEDBACK_BOT_NAME, settings.FEEDBACK_BOT)]
        create_users(realm, names, bot_type=UserProfile.DEFAULT_BOT)

        get_client("website")
        get_client("API")

        internal_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                         for bot in settings.INTERNAL_BOTS]
        create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
        # Set the owners for these bots to the bots themselves
        bots = UserProfile.objects.filter(email__in=[bot_info[1] for bot_info in internal_bots])
        for bot in bots:
            bot.bot_owner = bot
            bot.save()

        # Initialize the email gateway bot as an API Super User
        email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT)
        email_gateway_bot.is_api_super_user = True
        email_gateway_bot.save()

        self.stdout.write("Successfully populated database with initial data.\n")
        self.stdout.write("Please run ./manage.py generate_realm_creation_link "
                          "to generate link for creating organization")
