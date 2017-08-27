from __future__ import absolute_import
import datetime
import logging

from typing import Any, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.lib.digest import enqueue_emails, DIGEST_CUTOFF

## Logging setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.DIGEST_LOG_PATH)
file_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

class Command(BaseCommand):
    help = """Enqueue digest emails for users that haven't checked the app
in a while.
"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        cutoff = timezone_now() - datetime.timedelta(days=DIGEST_CUTOFF)
        enqueue_emails(cutoff)
