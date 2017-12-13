
import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError

from zerver.lib.logging_util import log_to_file
from zerver.models import UserProfile
from zproject.backends import ZulipLDAPUserPopulator

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.LDAP_SYNC_LOG_PATH)

# Run this on a cronjob to pick up on name changes.
def sync_ldap_user_data() -> None:
    logger.info("Starting update.")
    backend = ZulipLDAPUserPopulator()
    for u in UserProfile.objects.select_related().filter(is_active=True, is_bot=False).all():
        # This will save the user if relevant, and will do nothing if the user
        # does not exist.
        try:
            if backend.populate_user(backend.django_to_ldap_username(u.email)) is not None:
                logger.info("Updated %s." % (u.email,))
            else:
                logger.warning("Did not find %s in LDAP." % (u.email,))
        except IntegrityError:
            logger.warning("User populated did not match an existing user.")
    logger.info("Finished update.")

class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        sync_ldap_user_data()
