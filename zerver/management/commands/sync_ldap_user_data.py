import logging
from argparse import ArgumentParser
from typing import Any, Collection

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile
from zproject.backends import ZulipLDAPError, sync_user_from_ldap

## Setup ##
logger = logging.getLogger("zulip.sync_ldap_user_data")
log_to_file(logger, settings.LDAP_SYNC_LOG_PATH)


# Run this on a cron job to pick up on name changes.
@transaction.atomic
def sync_ldap_user_data(
    user_profiles: Collection[UserProfile], deactivation_protection: bool = True
) -> None:
    """
    Synchronize user data from LDAP.

    This function takes a collection of UserProfile objects as input and synchronizes
    the user data from the LDAP server. The function logs the start of the
    update and then proceeds to iterate over the user_profiles collection. For
    each user profile, it attempts to sync the user data from LDAP by calling
    the sync_user_from_ldap function.
    If an error occurs during the sync process, the error message is logged.
    After syncing all user profiles, the function checks for deactivation protection
    and raises an exception if all users or owners of realms would be deactivated.
    Finally, the function logs the completion of the update.

    Args:
        user_profiles (Collection[UserProfile]): A collection of UserProfile
            objects representing the users whose data needs to be synchronized
            from LDAP.
        deactivation_protection (bool, optional): Flag indicating whether
            deactivation protection should be enabled. Defaults to True.

    Raises:
        Exception: If deactivation protection is enabled and all users or owners of realms
            would be deactivated.

    Returns:
        None
    """
    logger.info("Starting update.")
    try:
        realms = {u.realm.string_id for u in user_profiles}

        for u in user_profiles:
            # This will save the user if relevant, and will do nothing if the user
            # does not exist.
            try:
                sync_user_from_ldap(u, logger)
            except ZulipLDAPError as e:
                logger.error("Error attempting to update user %s:", u.delivery_email)
                logger.error(e.args[0])

        if deactivation_protection:
            if not UserProfile.objects.filter(is_bot=False, is_active=True).exists():
                raise Exception(
                    "LDAP sync would have deactivated all users. This is most likely due "
                    "to a misconfiguration of LDAP settings. Rolling back...\n"
                    "Use the --force option if the mass deactivation is intended."
                )
            for string_id in realms:
                if not UserProfile.objects.filter(
                    is_bot=False,
                    is_active=True,
                    realm__string_id=string_id,
                    role=UserProfile.ROLE_REALM_OWNER,
                ).exists():
                    raise Exception(
                        f"LDAP sync would have deactivated all owners of realm {string_id}. "
                        "This is most likely due "
                        "to a misconfiguration of LDAP settings. Rolling back...\n"
                        "Use the --force option if the mass deactivation is intended."
                    )
    except Exception:
        logger.exception("LDAP sync failed")
        raise

    logger.info("Finished update.")


class Command(ZulipBaseCommand):
    """
    A command for handling a specific task in the Zulip application.
    """

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Add command line arguments to the parser object.

        Args:
            parser (ArgumentParser): The parser object.
        """
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Disable the protection against deactivating all users.",
        )

        self.add_realm_args(parser)
        self.add_user_list_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute the logic for the command.

        Args:
            args: Any positional arguments.
            options: Any keyword arguments.
        """
        if options.get("realm_id") is not None:
            realm = self.get_realm(options)
            user_profiles = self.get_users(options, realm, is_bot=False, include_deactivated=True)
        else:
            user_profiles = UserProfile.objects.select_related("realm").filter(is_bot=False)

            if not user_profiles.exists():
                # This case provides a special error message if one
                # tries setting up LDAP sync before creating a realm.
                raise CommandError("Zulip server contains no users. Have you created a realm?")

        if len(user_profiles) == 0:
            # We emphasize that this error is purely about the
            # command-line parameters, since this has nothing to do
            # with your LDAP configuration.
            raise CommandError("Zulip server contains no users matching command-line parameters.")

        sync_ldap_user_data(user_profiles, not options["force"])
