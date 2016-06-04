from __future__ import absolute_import
from __future__ import print_function

from optparse import make_option
from typing import Any

from django.core.management.base import BaseCommand
from django.conf import settings
import sys

class Command(BaseCommand):
    help = """Checks your Zulip Voyager Django configuration for issues."""

    option_list = BaseCommand.option_list + ()
    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        for (setting_name, default) in settings.REQUIRED_SETTINGS:
            try:
                if settings.__getattr__(setting_name) != default:
                    continue
            except AttributeError:
                pass

            print("Error: You must set %s in /etc/zulip/settings.py." % (setting_name,))
            sys.exit(1)
