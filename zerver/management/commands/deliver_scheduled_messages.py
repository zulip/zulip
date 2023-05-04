import logging
import time
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.scheduled_messages import send_scheduled_message
from zerver.lib.logging_util import log_to_file
from zerver.models import ScheduledMessage

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.DELIVER_SCHEDULED_MESSAGES_LOG_PATH)


class Command(BaseCommand):
    help = """Deliver scheduled messages from the ScheduledMessage table.
Run this command under supervisor.

This management command is run via supervisor.

Usage: ./manage.py deliver_scheduled_messages
"""

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            while True:
                with transaction.atomic():
                    messages_to_deliver = ScheduledMessage.objects.filter(
                        scheduled_timestamp__lte=timezone_now(), delivered=False
                    ).select_for_update()
                    for scheduled_message in messages_to_deliver:
                        send_scheduled_message(scheduled_message)

                cur_time = timezone_now()
                time_next_min = (cur_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_time = (time_next_min - cur_time).total_seconds()
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            pass
