
import logging

from argparse import ArgumentParser
from typing import Any, List


from django.conf import settings

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile
from zproject.backends import ZulipLDAPException, sync_user_from_ldap

## Setup ##
logger = logging.getLogger('zulip.sync_ldap_user_data')
log_to_file(logger, settings.LDAP_SYNC_LOG_PATH)

# Run this on a cronjob to pick up on name changes.
def sync_ldap_user_data(user_profiles: List[UserProfile]) -> None:
    logger.info("Starting update.")
    for u in user_profiles:
        # This will save the user if relevant, and will do nothing if the user
        # does not exist.
        try:
            if sync_user_from_ldap(u):
                logger.info("Updated %s." % (u.email,))
            else:
                logger.warning("Did not find %s in LDAP." % (u.email,))
                if settings.LDAP_DEACTIVATE_NON_MATCHING_USERS:
                    logger.info("Deactivated non-matching user: %s" % (u.email,))
        except ZulipLDAPException as e:
            logger.error("Error attempting to update user %s:" % (u.email,))
            logger.error(e)
    logger.info("Finished update.")

class Command(ZulipBaseCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser)
        self.add_user_list_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        if options.get('realm_id') is not None:
            realm = self.get_realm(options)
            user_profiles = self.get_users(options, realm, is_bot=False)
        else:
            user_profiles = UserProfile.objects.select_related().filter(is_bot=False)
        sync_ldap_user_data(user_profiles)
