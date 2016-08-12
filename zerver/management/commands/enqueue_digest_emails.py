from __future__ import absolute_import
import datetime
import pytz
import logging

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.queue import queue_json_publish
from zerver.models import UserActivity, UserProfile, get_realm, Realm

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
    most_recent_visit = [row.last_visit for row in \
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
    previous_day = datetime.datetime.now(tz=pytz.utc) - one_day
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

def domains_for_this_deployment():
    # type: () -> List[str]
    if settings.ZILENCER_ENABLED:
        # Voyager deployments don't have a Deployment entry.
        # Only send zulip.com digests on staging.
        from zilencer.models import Deployment
        site_url = settings.EXTERNAL_URI_SCHEME + settings.EXTERNAL_HOST.rstrip("/")
        try:
            deployment = Deployment.objects.select_related('realms').get(
                base_site_url__startswith=site_url)
        except Deployment.DoesNotExist:
            raise ValueError("digest: Unable to determine deployment.")

        return [r.domain for r in deployment.realms.all()]
    # Voyager and development.
    return []

def should_process_digest(domain, deployment_domains):
    # type: (str, List[str]) -> bool
    if domain in settings.SYSTEM_ONLY_REALMS:
        # Don't try to send emails to system-only realms
        return False
    if settings.PRODUCTION and not settings.VOYAGER:
        # zulip.com or staging.zulip.com
        return domain in deployment_domains
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
        if datetime.datetime.utcnow().weekday() not in VALID_DIGEST_DAYS:
            return

        deployment_domains = domains_for_this_deployment()
        for realm in Realm.objects.filter(deactivated=False, show_digest_email=True):
            domain = realm.domain
            if not should_process_digest(domain, deployment_domains):
                continue

            user_profiles = UserProfile.objects.filter(
                realm=get_realm(domain), is_active=True, is_bot=False,
                enable_digest_emails=True)

            for user_profile in user_profiles:
                cutoff = last_business_day()
                if inactive_since(user_profile, cutoff):
                    queue_digest_recipient(user_profile, cutoff)
                    logger.info("%s is inactive, queuing for potential digest" % (
                            user_profile.email,))
