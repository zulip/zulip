from typing import Any

from django.utils.timezone import now as timezone_now

from zerver.actions.realm_settings import scrub_deactivated_realm
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Realm


class Command(ZulipBaseCommand):
    help = """Clears data of deactivated realms."""

    def handle(self, *args: Any, **options: Any) -> None:
        realms_to_scrub = Realm.objects.filter(
            deactivated=True,
            scheduled_deletion_date__lte=timezone_now(),
        )
        for realm in realms_to_scrub:
            scrub_deactivated_realm(realm)
