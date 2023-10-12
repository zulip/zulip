from typing import Any

from typing_extensions import override

from zerver.actions.user_groups import promote_new_full_members
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Add users to full members system group."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        promote_new_full_members()
