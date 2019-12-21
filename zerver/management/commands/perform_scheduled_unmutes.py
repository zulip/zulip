import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.actions import do_unmute_topic
from zerver.lib.management import sleep_forever
from zerver.models import MutedTopic

class Command(BaseCommand):
    help = """Perform scheduled unmute operation from the MutedTopics table.
Usage: ./manage.py perform_scheduled_unmutes
"""

    def handle(self, *args: Any, **options: Any) -> None:
        if settings.EMAIL_DELIVERER_DISABLED:
            sleep_forever()

        while True:
            muted_topics = MutedTopic.objects.filter(
                scheduled_timestamp__lte=timezone_now())
            if muted_topics:
                for muted_topic in muted_topics:
                    if muted_topic.scheduled_timestamp is not None:
                        with transaction.atomic():
                            do_unmute_topic(muted_topic.user_profile,
                                            muted_topic.stream,
                                            muted_topic.topic_name)
                time.sleep(10)
            else:
                time.sleep(2)
