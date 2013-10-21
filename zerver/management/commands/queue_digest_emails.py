from __future__ import absolute_import
import datetime
import pytz

from django.core.management.base import BaseCommand

from zerver.lib.queue import queue_json_publish
from zerver.models import UserActivity, get_user_profile_by_email

VALID_DIGEST_DAYS = (1, 2, 3)
def inactive_since(user_profile, cutoff):
    # Hasn't used the app in the last 24 business-day hours.
    most_recent_visit = [row.last_visit for row in \
                             UserActivity.objects.filter(
            user_profile=user_profile)]

    if not most_recent_visit:
        # This person has never used the app.
        return True

    last_visit = max(most_recent_visit)
    return last_visit < cutoff

def last_business_day():
    one_day = datetime.timedelta(hours=24)
    previous_day = datetime.datetime.now(tz=pytz.utc) - one_day
    while previous_day.weekday() not in VALID_DIGEST_DAYS:
        previous_day -= one_day
    return previous_day

# Changes to this should also be reflected in
# zerver/worker/queue_processors.py:DigestWorker.consume()
def queue_digest_recipient(user_profile, cutoff):
    # Convert cutoff to epoch seconds for transit.
    event = {"user_profile_id": user_profile.id,
             "cutoff": cutoff.strftime('%s')}
    queue_json_publish("digest_emails", event, lambda event: None)

class Command(BaseCommand):
    help = """Enqueue digest emails for users that haven't checked the app
in a while.
"""
    def handle(self, *args, **options):
        # To be really conservative while we don't have user timezones or
        # special-casing for companies with non-standard workweeks, only
        # try to send mail on Tuesdays, Wednesdays, and Thursdays.
        if datetime.datetime.utcnow().weekday() not in VALID_DIGEST_DAYS:
            return

        for email in ["jesstess@zulip.com", "jessica.mckellar@gmail.com",
                      "sipbtest@mit.edu", "jesstess+si@zulip.com"]:
            user_profile = get_user_profile_by_email(email)
            cutoff = last_business_day()
            if inactive_since(user_profile, cutoff):
                queue_digest_recipient(user_profile, cutoff)
