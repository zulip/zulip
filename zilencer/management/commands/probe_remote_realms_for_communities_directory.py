from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_unless_locked
from zilencer.lib.communities_directory import check_remote_realms_active_for_communities_directory


class Command(ZulipBaseCommand):
    help = "Check which remote organizations asking to be advertised are still reachable"

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        check_remote_realms_active_for_communities_directory()
