#!/usr/bin/env python3

"""
Shows backlog count of ScheduledEmail
"""

from __future__ import absolute_import
from __future__ import print_function

from typing import Any
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.models import ScheduledEmail

from datetime import timedelta

class Command(BaseCommand):
    help = """Shows backlog count of ScheduledEmail
(The number of currently overdue (by at least a minute) email jobs)

This is run as part of the nagios health check for the deliver_email command.

Usage: ./manage.py print_email_delivery_backlog
"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        print(ScheduledEmail.objects.filter(
            scheduled_timestamp__lte=timezone_now()-timedelta(minutes=1)).count())
