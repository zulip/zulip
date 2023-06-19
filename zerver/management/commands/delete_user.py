from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.actions.users import do_delete_user
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.users import get_active_bots_owned_by_user


class Command(ZulipBaseCommand):
    help = """

Delete a user or users, including all messages sent by them and
personal messages received by them, and audit records, like what
streams they had been subscribed to. Deactivating users is generally
recommended over this tool, but deletion can be useful if you
specifically to completely delete an account created for testing.
This will:

* Delete the user's account, including metadata like name, email
  address, custom profile fields, historical subscriptions, etc.

* Delete any messages they've sent and any non-group direct messages
  they've received.

* Group direct messages in which the user participated won't be
  deleted (with the exceptions of those message the deleted user
  sent). An inactive, inaccessible dummy user account named "Deleted
  User <id>" is created to replace the deleted user as a recipient in
  group direct message conversations, in order to somewhat preserve
  their integrity.

* Delete other records of the user's activity, such as emoji reactions.

* Deactivate all bots owned by the user, without deleting them or
  their data.  If you want to delete the bots and the message
  sent/received by them, you can use the command on them individually.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-f",
            "--for-real",
            action="store_true",
            help="Actually delete the user(s). Default is a dry run.",
        )
        self.add_realm_args(parser)
        self.add_user_list_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        user_profiles = self.get_users(options, realm)

        for user_profile in user_profiles:
            print(
                "{} has {} active bots that will be deactivated as a result of the user's deletion.".format(
                    user_profile.delivery_email,
                    get_active_bots_owned_by_user(user_profile).count(),
                )
            )

        if not options["for_real"]:
            raise CommandError("This was a dry run. Pass -f to actually delete.")

        for user_profile in user_profiles:
            do_delete_user(user_profile, acting_user=None)
            print(f"Successfully deleted user {user_profile.delivery_email}.")
