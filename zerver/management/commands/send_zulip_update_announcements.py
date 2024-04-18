from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from typing_extensions import override

from scripts.lib.zulip_tools import ENDC, WARNING
from zerver.lib.context_managers import lockfile_nonblocking
from zerver.lib.management import ZulipBaseCommand
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
    def handle(self, *args: Any, **options: Any) -> None:
        with lockfile_nonblocking(
            settings.ZULIP_UPDATE_ANNOUNCEMENTS_LOCK_FILE,
        ) as lock_acquired:
            if lock_acquired:
                send_zulip_update_announcements(skip_delay=options["skip_delay"])
            else:
                print(
                    f"{WARNING}Update announcements lock {settings.ZULIP_UPDATE_ANNOUNCEMENTS_LOCK_FILE} is unavailable;"
                    f" exiting.{ENDC}"
                )
