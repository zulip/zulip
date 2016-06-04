from __future__ import absolute_import

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.conf import settings

from zproject.backends import ZulipLDAPUserPopulator
from zerver.models import UserProfile

## Setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.LDAP_SYNC_LOG_PATH)
file_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

# Run this on a cronjob to pick up on name changes.
def sync_ldap_user_data():
    # type: () -> None
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
    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        sync_ldap_user_data()
