#!/usr/bin/env python

"""
Shows backlog count of ScheduledJobs of type Email
"""

from __future__ import absolute_import
from __future__ import print_function

from typing import Any
from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.models import ScheduledJob

from datetime import datetime, timedelta

class Command(BaseCommand):
    help = """Shows backlog count of ScheduledJobs of type Email
(The number of currently overdue (by at least a minute) email jobs)

This is run as part of the nagios health check for the deliver_email command.
Please note that this is only relevant to the SMTP-based email delivery (no Mandrill).

Usage: python manage.py print_email_delivery_backlog
"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        print(len(ScheduledJob.objects.filter(type=ScheduledJob.EMAIL,
                                                  scheduled_timestamp__lte=datetime.utcnow()-timedelta(minutes=1))))
