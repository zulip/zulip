
from typing import Any, Iterable, Text, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.actions import create_users
from zerver.models import Realm, UserProfile

class Command(BaseCommand):
    help = "Create Realm internal bots. These bots provide various services like doing reminders."

    def handle(self, *args: Any, **options: Any) -> None:
        internal_bots = set([(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                            for bot in settings.REALM_INTERNAL_BOTS])

        existing_bots = list(UserProfile.objects.select_related(
            'realm').filter(email__in=[bot[1] for bot in internal_bots]))

        all_realms = list(Realm.objects.all())

        for realm in all_realms:
            this_realm_bots = set()
            for bot in existing_bots:
                if bot.realm.string_id == realm.string_id:
                    this_realm_bots.update([bot])
            bots_to_create = list(internal_bots - this_realm_bots)
            if bots_to_create:
                create_users(realm, bots_to_create, bot_type=UserProfile.DEFAULT_BOT)

        # Set the owners for these bots to the bots themselves
        bots = UserProfile.objects.filter(
            email__in=[bot_info[1] for bot_info in internal_bots],
            bot_owner__isnull=True
        )
        for bot in bots:
            bot.bot_owner = bot
            bot.save()

        self.stdout.write("Successfully created realm default bots.\n")
