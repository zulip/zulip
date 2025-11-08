from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, check_config


class Command(ZulipBaseCommand):
    help = """Checks /etc/zulip/settings.py for common configuration issues."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        check_config()
