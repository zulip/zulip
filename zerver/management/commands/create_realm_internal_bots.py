
from typing import Any, Iterable, Text, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from zerver.lib.onboarding import setup_realm_internal_bots
from zerver.models import Realm, UserProfile

class Command(BaseCommand):
    help = """\
Create realm internal bots if absent, in all realms.

These are normally created when the realm is, so this should be a no-op
except when upgrading to a version that adds a new realm internal bot.
"""

    @staticmethod
    def missing_any_bots() -> bool:
        bot_emails = [bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,)
                      for bot in settings.REALM_INTERNAL_BOTS]
        bot_counts = dict(UserProfile.objects.filter(email__in=bot_emails)
                                             .values_list('email')
                                             .annotate(Count('id')))
        realm_count = Realm.objects.count()
        return any(bot_counts.get(email, 0) < realm_count for email in bot_emails)

    def handle(self, *args: Any, **options: Any) -> None:
        if self.missing_any_bots():
            for realm in Realm.objects.all():
                setup_realm_internal_bots(realm)
                # create_users is idempotent -- it's a no-op when a given email
                # already has a user in a given realm.
