from typing import Any

from django.core.management.base import BaseCommand

from zerver.lib.management import check_config


class Command(BaseCommand):
    """Checks /etc/zulip/settings.py for common configuration issues."""
    help = """Checks /etc/zulip/settings.py for common configuration issues."""

    def handle(self, *args: Any, **options: Any) -> None:
        check_config()
