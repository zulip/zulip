from __future__ import absolute_import
import datetime
import logging

from typing import Any, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.lib.queue import queue_json_publish
from zerver.models import UserProfile, Realm
from zerver.lib.digest import inactive_since, should_process_digest

## Logging setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.DIGEST_LOG_PATH)
file_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

VALID_DIGEST_DAY = 1  # Tuesdays
DIGEST_CUTOFF = 5

# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:DigestWorker.consume()
def queue_digest_recipient(user_profile, cutoff):
    # type: (UserProfile, datetime.datetime) -> None
    # Convert cutoff to epoch seconds for transit.
    event = {"user_profile_id": user_profile.id,
             "cutoff": cutoff.strftime('%s')}
    queue_json_publish("digest_emails", event, lambda event: None)

class Command(BaseCommand):
    help = """Enqueue digest emails for users that haven't checked the app
in a while.
"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        # To be really conservative while we don't have user timezones or
        # special-casing for companies with non-standard workweeks, only
        # try to send mail on Tuesdays.
        if timezone_now().weekday() != VALID_DIGEST_DAY:
            return

        for realm in Realm.objects.filter(deactivated=False, show_digest_email=True):
            if not should_process_digest(realm.string_id):
                continue

            user_profiles = UserProfile.objects.filter(
                realm=realm, is_active=True, is_bot=False, enable_digest_emails=True)

            for user_profile in user_profiles:
                cutoff = timezone_now() - datetime.timedelta(days=DIGEST_CUTOFF)
                if inactive_since(user_profile, cutoff):
                    queue_digest_recipient(user_profile, cutoff)
                    logger.info("%s is inactive, queuing for potential digest" % (
                        user_profile.email,))
