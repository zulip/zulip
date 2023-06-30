"""\
Send email messages that have been queued for later delivery by
various things (e.g. invitation reminders and welcome emails).

This management command is run via supervisor.
"""
import logging
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.logging_util import log_to_file
from zerver.lib.send_email import EmailNotDeliveredError, deliver_scheduled_emails
from zerver.models import ScheduledEmail

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.EMAIL_DELIVERER_LOG_PATH)


class Command(BaseCommand):
    help = """Send emails queued by various parts of Zulip
for later delivery.

Run this command under supervisor.

Usage: ./manage.py deliver_scheduled_emails
"""

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            while True:
                with transaction.atomic():
                    job = (
                        ScheduledEmail.objects.filter(scheduled_timestamp__lte=timezone_now())
                        .prefetch_related("users")
                        .select_for_update(skip_locked=True)
                        .order_by("scheduled_timestamp")
                        .first()
                    )
                    if job:
                        try:
                            deliver_scheduled_emails(job)
                        except EmailNotDeliveredError:
                            logger.warning("%r not delivered", job)
                    else:
                        time.sleep(10)
        except KeyboardInterrupt:
            pass
