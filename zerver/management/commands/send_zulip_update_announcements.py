from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_unless_locked
from zerver.lib.zulip_update_announcements import send_zulip_update_announcements


class Command(ZulipBaseCommand):
    help = """Script to send zulip update announcements to realms."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--skip-delay",
            action="store_true",
            help="Immediately send updates if 'zulip_update_announcements_stream' is configured.",
        )

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        send_zulip_update_announcements(skip_delay=options["skip_delay"])
