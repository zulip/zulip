import logging
import time
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.user_status import try_clear_scheduled_user_status
from zerver.lib.logging_util import log_to_file

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.CLEAR_USER_STATUS_LOG_PATH)


class Command(BaseCommand):
    help = """Clear user's status for later expiry.

Run this command under supervisor.

Usage: ./manage.py clear_user_status
"""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        try:
            while True:
                if try_clear_scheduled_user_status():
                    continue

                # If there's no overdue statuses, go to sleep until the next minute.
                cur_time = timezone_now()
                time_next_min = (cur_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_time = (time_next_min - cur_time).total_seconds()
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            pass
