import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Max

from zerver.models import Huddle, UserProfile, bulk_get_huddle_user_ids, get_huddle_hash


class Command(BaseCommand):
    def handle(self, *args: Any, **options: str) -> None:
        cross_realm_bot_ids = UserProfile.objects.filter(
            email__in=settings.CROSS_REALM_BOT_EMAILS
        ).values_list("id", flat=True)

        BATCH_SIZE = 1000
        id_lower_bound = 0

        max_id = Huddle.objects.all().aggregate(Max("id"))["id__max"]

        while id_lower_bound <= max_id:
            id_upper_bound = id_lower_bound + BATCH_SIZE + 1

            huddles = Huddle.objects.filter(
                id__gt=id_lower_bound, id__lt=id_upper_bound
            ).select_related("recipient")
            huddle_recipients = [huddle.recipient for huddle in huddles]
            huddle_recipient_id_to_user_ids_map = bulk_get_huddle_user_ids(huddle_recipients)

            for huddle in huddles:
                huddle_user_ids = huddle_recipient_id_to_user_ids_map[huddle.recipient_id]
                if not any(id in huddle_user_ids for id in cross_realm_bot_ids):
                    continue
                if huddle.huddle_hash == get_huddle_hash(huddle_user_ids):
                    continue

                print(f"Huddle {huddle.id} is broken and has a cross-realm bot participant")

            id_lower_bound += BATCH_SIZE
            time.sleep(0.1)
