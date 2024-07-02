import logging
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
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
                else:
                    time.sleep(10)
        except KeyboardInterrupt:
            pass
