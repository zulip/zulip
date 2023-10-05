from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

from zerver.actions.realm_settings import do_delete_all_realm_attachments
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Message, UserProfile


class Command(ZulipBaseCommand):
    """Script to permanently delete a realm. Recommended only for removing
    realms used for testing; consider using deactivate_realm instead."""
    help = """Script to permanently delete a realm. Recommended only for removing
realms used for testing; consider using deactivate_realm instead."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add command line arguments to the script.

        Args:
            parser (ArgumentParser): The argument parser object.
        """
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: str) -> None:
        """
        Handle the command with the provided arguments and options.

        This function performs various operations based on the provided options. It
        retrieves a realm based on the options, counts the number of active
        non-bot users in the realm, counts the number of messages in the realm,
        and prints the counts. If billing is enabled, it checks if the realm has a
        billing relationship associated with it and raises an error if it does. It
        then asks for confirmation to delete the realm and deletes the realm along
        with its attachments. Finally, it prints a success message.

        Args:
            args: Any additional arguments passed to the function.
            options (str): Additional options passed to the function as keyword arguments.

        Returns:
            None
        """
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        user_count = UserProfile.objects.filter(
            realm_id=realm.id,
            is_active=True,
            is_bot=False,
        ).count()

        message_count = Message.objects.filter(realm=realm).count()

        print(f"This realm has {user_count} users and {message_count} messages.\n")

        if settings.BILLING_ENABLED:
            # Deleting a Realm object also deletes associating billing
            # metadata in an invariant-violating way, so we should
            # never use this tool for a realm with billing set up.
            from corporate.models import CustomerPlan, get_customer_by_realm

            customer = get_customer_by_realm(realm)
            if customer and (
                customer.stripe_customer_id
                or CustomerPlan.objects.filter(customer=customer).exists()
            ):
                raise CommandError("This realm has had a billing relationship associated with it!")

        print(
            "This command will \033[91mPERMANENTLY DELETE\033[0m all data for this realm.  "
            "Most use cases will be better served by scrub_realm and/or deactivate_realm."
        )

        confirmation = input("Type the name of the realm to confirm: ")
        if confirmation != realm.string_id:
            raise CommandError("Aborting!")

        # Explicitly remove the attachments and their files in backend
        # storage; failing to do this leaves dangling files
        do_delete_all_realm_attachments(realm)

        # TODO: This approach leaks Recipient and Huddle objects,
        # because those don't have a foreign key to the Realm or any
        # other model it cascades to (Realm/Stream/UserProfile/etc.).
        realm.delete()

        print("Realm has been successfully permanently deleted.")
