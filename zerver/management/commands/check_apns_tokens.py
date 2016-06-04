from __future__ import absolute_import

from typing import Any

from django.core.management.base import BaseCommand
from zerver.lib.push_notifications import check_apns_feedback

class Command(BaseCommand):
    help = """Checks the Apple Push Notifications Service for any tokens that have been
              invalidated, and removes them from the database.

    Usage: ./manage.py check_apns_tokens"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        check_apns_feedback()
