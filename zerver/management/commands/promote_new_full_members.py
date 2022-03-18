from typing import Any

from zerver.lib.actions import promote_new_full_members
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Add users to full members system group."""

    def handle(self, *args: Any, **options: Any) -> None:
        promote_new_full_members()
