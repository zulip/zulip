from __future__ import absolute_import

from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings
import sys

class Command(BaseCommand):
    help = """Checks your Zulip Enterprise Django configuration for issues."""

    option_list = BaseCommand.option_list + ()
    def handle(self, **options):
        for (setting_name, default) in settings.REQUIRED_SETTINGS:
            try:
                if settings.__getattr__(setting_name) != default:
                    continue
            except AttributeError:
                pass

            print "Error: You must set %s in /etc/zulip/settings.py." % (setting_name,)
            sys.exit(1)
