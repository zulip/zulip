"""\
Send email messages that have been queued for later delivery by
various things (at this time invitation reminders and day1/day2
followup emails).

This management command is run via supervisor.  Do not run on multiple
machines, as you may encounter multiple sends in a specific race
condition.  (Alternatively, you can set `EMAIL_DELIVERER_DISABLED=True`
on all but one machine to make the command have no effect.)

"""
import logging
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import sleep_forever
from zerver.lib.send_email import EmailNotDeliveredException, deliver_scheduled_emails
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

        if settings.EMAIL_DELIVERER_DISABLED:
            sleep_forever()

        while True:
            found_rows = False
            with transaction.atomic():
                email_jobs_to_deliver = (
                    ScheduledEmail.objects.filter(scheduled_timestamp__lte=timezone_now())
                    .prefetch_related("users")
                    .select_for_update()
                )
                if email_jobs_to_deliver:
                    found_rows = True
                    for job in email_jobs_to_deliver:
                        try:
                            deliver_scheduled_emails(job)
                        except EmailNotDeliveredException:
                            logger.warning("%r not delivered", job)
            # Less load on the db during times of activity,
            # and more responsiveness when the load is low
            if found_rows:
                time.sleep(10)
            else:
                time.sleep(2)
