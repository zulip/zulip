import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.digest import DIGEST_CUTOFF, enqueue_emails
from zerver.lib.logging_util import log_to_file
from zerver.lib.management import abort_unless_locked

## Logging setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)


class Command(BaseCommand):
    help = """Enqueue digest emails for users that haven't checked the app
in a while.
"""

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone_now() - timedelta(days=DIGEST_CUTOFF)
        enqueue_emails(cutoff)
