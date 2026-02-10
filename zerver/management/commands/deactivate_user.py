from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.users import do_deactivate_user
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.sessions import user_sessions
from zerver.lib.users import get_active_bots_owned_by_user


class Command(ZulipBaseCommand):
    help = "Deactivate a user, including forcibly logging them out."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-f",
            "--for-real",
            action="store_true",
            help="Actually deactivate the user. Default is a dry run.",
        )
        parser.add_argument("email", metavar="<email>", help="email of user to deactivate")
        self.add_realm_args(parser)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        user_profile = self.get_user(options["email"], realm)

        print(
            f"Deactivating {user_profile.full_name} ({user_profile.delivery_email}) - {user_profile.realm.string_id}"
        )
        print(f"{user_profile.delivery_email} has the following active sessions:")
        for session in user_sessions(user_profile):
            print(session.expire_date, session.get_decoded())
        print()
        print(
            f"{user_profile.delivery_email} has {get_active_bots_owned_by_user(user_profile).count()} active bots that will also be deactivated."
        )

        if not options["for_real"]:
            raise CommandError("This was a dry run. Pass -f to actually deactivate.")

        do_deactivate_user(user_profile, acting_user=None)
        print("Sessions deleted, user deactivated.")
