import logging
from argparse import ArgumentParser
from typing import Any, List

from django.conf import settings
from django.db import transaction

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile
from zproject.backends import ZulipLDAPException, sync_user_from_ldap

## Setup ##
logger = logging.getLogger('zulip.sync_ldap_user_data')
log_to_file(logger, settings.LDAP_SYNC_LOG_PATH)

# Run this on a cronjob to pick up on name changes.
def sync_ldap_user_data(user_profiles: List[UserProfile], deactivation_protection: bool=True) -> None:
    logger.info("Starting update.")
    with transaction.atomic():
        realms = {u.realm.string_id for u in user_profiles}

        for u in user_profiles:
            # This will save the user if relevant, and will do nothing if the user
            # does not exist.
            try:
                sync_user_from_ldap(u, logger)
            except ZulipLDAPException as e:
                logger.error("Error attempting to update user %s:", u.delivery_email)
                logger.error(e.args[0])

        if deactivation_protection:
            if not UserProfile.objects.filter(is_bot=False, is_active=True).exists():
                error_msg = ("Ldap sync would have deactivated all users. This is most likely due " +
                             "to a misconfiguration of LDAP settings. Rolling back...\n" +
                             "Use the --force option if the mass deactivation is intended.")
                logger.error(error_msg)
                # Raising an exception in this atomic block will rollback the transaction.
                raise Exception(error_msg)
            for string_id in realms:
                if not UserProfile.objects.filter(is_bot=False, is_active=True, realm__string_id=string_id,
                                                  role__gte=UserProfile.ROLE_REALM_ADMINISTRATOR).exists():
                    error_msg = ("Ldap sync would have deactivated all administrators of realm %s. " +
                                 "This is most likely due " +
                                 "to a misconfiguration of LDAP settings. Rolling back...\n" +
                                 "Use the --force option if the mass deactivation is intended.")
                    error_msg = error_msg % (string_id,)
                    logger.error(error_msg)
                    raise Exception(error_msg)

    logger.info("Finished update.")

class Command(ZulipBaseCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-f', '--force',
                            action="store_true",
                            help='Disable the protection against deactivating all users.')

        self.add_realm_args(parser)
        self.add_user_list_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        if options.get('realm_id') is not None:
            realm = self.get_realm(options)
            user_profiles = self.get_users(options, realm, is_bot=False,
                                           include_deactivated=True)
        else:
            user_profiles = UserProfile.objects.select_related().filter(is_bot=False)
        sync_ldap_user_data(user_profiles, not options['force'])
