from __future__ import absolute_import
import datetime
import logging

from typing import Any, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now as timezone_now

from zerver.lib.queue import queue_json_publish
from zerver.models import UserActivity, UserProfile, Realm

## Logging setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.DIGEST_LOG_PATH)
file_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


VALID_DIGEST_DAYS = (1, 2, 3, 4)
def inactive_since(user_profile, cutoff):
    # type: (UserProfile, datetime.datetime) -> bool
    # Hasn't used the app in the last 24 business-day hours.
    most_recent_visit = [row.last_visit for row in
                         UserActivity.objects.filter(
                             user_profile=user_profile)]

    if not most_recent_visit:
        # This person has never used the app.
        return True

    last_visit = max(most_recent_visit)
    return last_visit < cutoff

def last_business_day():
    # type: () -> datetime.datetime
    one_day = datetime.timedelta(hours=23)
    previous_day = timezone_now() - one_day
    while previous_day.weekday() not in VALID_DIGEST_DAYS:
        previous_day -= one_day
    return previous_day

# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:DigestWorker.consume()
def queue_digest_recipient(user_profile, cutoff):
    # type: (UserProfile, datetime.datetime) -> None
    # Convert cutoff to epoch seconds for transit.
    event = {"user_profile_id": user_profile.id,
             "cutoff": cutoff.strftime('%s')}
    queue_json_publish("digest_emails", event, lambda event: None)

def should_process_digest(realm_str):
    # type: (str) -> bool
    if realm_str in settings.SYSTEM_ONLY_REALMS:
        # Don't try to send emails to system-only realms
        return False
    return True

class Command(BaseCommand):
    help = """Enqueue digest emails for users that haven't checked the app
in a while.
"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        # To be really conservative while we don't have user timezones or
        # special-casing for companies with non-standard workweeks, only
        # try to send mail on Tuesdays, Wednesdays, and Thursdays.
        if timezone_now().weekday() not in VALID_DIGEST_DAYS:
            return

        for realm in Realm.objects.filter(deactivated=False, show_digest_email=True):
            if not should_process_digest(realm.string_id):
                continue

            user_profiles = UserProfile.objects.filter(
                realm=realm, is_active=True, is_bot=False, enable_digest_emails=True)

            for user_profile in user_profiles:
                cutoff = last_business_day()
                if inactive_since(user_profile, cutoff):
                    queue_digest_recipient(user_profile, cutoff)
                    logger.info("%s is inactive, queuing for potential digest" % (
                        user_profile.email,))
