
"""\
Deliver email messages that have been queued by various things
(at this time invitation reminders and day1/day2 followup emails).

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
from django.utils.timezone import now as timezone_now
from ujson import loads

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import sleep_forever
from zerver.lib.send_email import EmailNotDeliveredException, send_email, \
    handle_send_email_format_changes
from zerver.models import ScheduledEmail

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.EMAIL_DELIVERER_LOG_PATH)

class Command(BaseCommand):
    help = """Deliver emails queued by various parts of Zulip
(either for immediate sending or sending at a specified time).

Run this command under supervisor. This is for SMTP email delivery.

Usage: ./manage.py deliver_email
"""

    def handle(self, *args: Any, **options: Any) -> None:

        if settings.EMAIL_DELIVERER_DISABLED:
            sleep_forever()

        while True:
            email_jobs_to_deliver = ScheduledEmail.objects.filter(
                scheduled_timestamp__lte=timezone_now())
            if email_jobs_to_deliver:
                for job in email_jobs_to_deliver:
                    data = loads(job.data)
                    handle_send_email_format_changes(data)
                    try:
                        send_email(**data)
                        job.delete()
                    except EmailNotDeliveredException:
                        logger.warning("%r not delivered" % (job,))
                time.sleep(10)
            else:
                # Less load on the db during times of activity,
                # and more responsiveness when the load is low
                time.sleep(2)
