import datetime
from typing import Any, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.lib.digest import DIGEST_CUTOFF, enqueue_emails
from zerver.lib.logging_util import create_logger

## Logging setup ##
logger = create_logger(__name__, settings.DIGEST_LOG_PATH)

class Command(BaseCommand):
    help = """Enqueue digest emails for users that haven't checked the app
in a while.
"""

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone_now() - datetime.timedelta(days=DIGEST_CUTOFF)
        enqueue_emails(cutoff)
