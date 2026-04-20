import time
from datetime import timedelta
from typing import Any

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.recurring_scheduled_messages import try_deliver_one_recurring_scheduled_message
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Deliver recurring scheduled messages from the RecurringScheduledMessage table.

This management command is run via supervisor as a long-running daemon.
It polls for due jobs every minute and delivers each one to all its destinations.

Usage: ./manage.py deliver_recurring_scheduled_messages
"""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        try:
            while True:
                if try_deliver_one_recurring_scheduled_message():
                    # A job was found and processed; immediately check for more
                    # in case several jobs were due at the same time.
                    continue

                # Nothing due right now — sleep until the start of the next minute.
                cur_time = timezone_now()
                time_next_min = (cur_time + timedelta(minutes=1)).replace(
                    second=0, microsecond=0
                )
                sleep_time = (time_next_min - cur_time).total_seconds()
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            pass
