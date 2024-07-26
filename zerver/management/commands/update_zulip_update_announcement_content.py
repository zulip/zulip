from typing import Any

from typing_extensions import override
from argparse import ArgumentParser

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.zulip_update_announcements import update_zulip_update_announcement_content


class Command(ZulipBaseCommand):
    help = """Script to update the content of a zulip update announcement."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--level",
            type=int,
            required=True,
            help="The level whose content needs to be updated.",
        )

        parser.add_argument(
            "--old-content",
            type=str,
            required=True,
            help="The old announcement content which needs to be updated."
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        update_zulip_update_announcement_content(options["level"], options["old_content"])
