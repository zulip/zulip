from typing import Any

from zerver.actions.user_groups import promote_new_full_members
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    """
    Add users to full members system group.
    """
    help = """Add users to full members system group."""

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute the command to add users to the full members system group.

        This method calls the `promote_new_full_members` function from the
        `zerver.actions.user_groups` module to add users to the full members system
        group.

        Args:
            *args: Any additional arguments
            **options: Any additional keyword arguments
            """
        promote_new_full_members()
