import time
from datetime import timedelta
from typing import Any

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.scheduled_messages import try_deliver_one_scheduled_message
from zerver.lib.management import ZulipBaseCommand


## Setup ##
class Command(ZulipBaseCommand):
    help = """Deliver scheduled messages from the ScheduledMessage table.
Run this command under supervisor.

This management command is run via supervisor.

Usage: ./manage.py deliver_scheduled_messages
"""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        try:
            while True:
                if try_deliver_one_scheduled_message():
                    continue

                # If there's no overdue scheduled messages, go to sleep until the next minute.
                cur_time = timezone_now()
                time_next_min = (cur_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_time = (time_next_min - cur_time).total_seconds()
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            pass
