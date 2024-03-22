from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.zulip_update_announcements import send_zulip_update_announcements


class Command(ZulipBaseCommand):
    help = """Script to send zulip update announcements to realms."""

    @override
    def handle(self, *args: Any, **options: str) -> None:
        send_zulip_update_announcements()
