from typing import Any

from django.core.management.base import BaseCommand
from typing_extensions import override

from zerver.lib.management import check_config


class Command(BaseCommand):
    help = """Checks /etc/zulip/settings.py for common configuration issues."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        check_config()
