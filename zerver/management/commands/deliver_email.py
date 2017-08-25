#!/usr/bin/env python3

"""\
Deliver email messages that have been queued by various things
(at this time invitation reminders and day1/day2 followup emails).

This management command is run via supervisor.  Do not run on multiple
machines, as you may encounter multiple sends in a specific race
condition.  (Alternatively, you can set `EMAIL_DELIVERER_DISABLED=True`
on all but one machine to make the command have no effect.)
"""

from __future__ import absolute_import

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.models import ScheduledEmail
from zerver.lib.context_managers import lockfile
from zerver.lib.send_email import send_email, EmailNotDeliveredException

import time
from zerver.lib.logging_util import create_logger
from datetime import datetime
from ujson import loads
from typing import Any

## Setup ##
logger = create_logger(__name__, settings.EMAIL_DELIVERER_LOG_PATH, 'DEBUG')

class Command(BaseCommand):
    help = """Deliver emails queued by various parts of Zulip
(either for immediate sending or sending at a specified time).

Run this command under supervisor. This is for SMTP email delivery.

Usage: ./manage.py deliver_email
"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None

        if settings.EMAIL_DELIVERER_DISABLED:
            while True:
                time.sleep(10*9)

        with lockfile("/tmp/zulip_email_deliver.lockfile"):
            while True:
                email_jobs_to_deliver = ScheduledEmail.objects.filter(scheduled_timestamp__lte=timezone_now())
                if email_jobs_to_deliver:
                    for job in email_jobs_to_deliver:
                        try:
                            send_email(**loads(job.data))
                            job.delete()
                        except EmailNotDeliveredException:
                            logger.warn("%r not delivered" % (job,))
                    time.sleep(10)
                else:
                    # Less load on the db during times of activity, and more responsiveness when the load is low
                    time.sleep(2)
