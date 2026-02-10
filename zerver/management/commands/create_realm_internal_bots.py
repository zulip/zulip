from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.onboarding import create_if_missing_realm_internal_bots


class Command(ZulipBaseCommand):
    help = """\
Create realm internal bots if absent, in all realms.

These are normally created when the realm is, so this should be a no-op
except when upgrading to a version that adds a new realm internal bot.
"""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        create_if_missing_realm_internal_bots()
        # create_users is idempotent -- it's a no-op when a given email
        # already has a user in a given realm.
