from __future__ import absolute_import

import time
import simplejson

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.conf import settings

from zephyr.lib.queue import SimpleQueueClient
from zephyr.lib.actions import handle_missedmessage_emails

class Command(BaseCommand):
    def handle(self, *args, **options):
        q = SimpleQueueClient()
        while True:
            missed_events = q.drain_queue("missedmessage_emails", json=True)
            by_recipient = defaultdict(list)

            for event in missed_events:
                by_recipient[event['user_profile_id']].append(event)

            for user_profile_id, events in by_recipient.items():
                handle_missedmessage_emails(user_profile_id, events)

            # Aggregate all messages received every 2 minutes to let someone finish sending a batch
            # of messages
            time.sleep(2 * 60)
