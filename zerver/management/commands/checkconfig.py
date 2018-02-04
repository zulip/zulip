
import sys
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = """Checks your Zulip Voyager Django configuration for issues."""

    def handle(self, *args: Any, **options: Any) -> None:
        for (setting_name, default) in settings.REQUIRED_SETTINGS:
            try:
                if settings.__getattr__(setting_name) != default:
                    continue
            except AttributeError:
                pass

            print("Error: You must set %s in /etc/zulip/settings.py." % (setting_name,))
            sys.exit(1)
