from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = """Send some stats to statsd.

Usage: python manage.py send_stats [incr|decr|timing|timer|gauge] name val"""

    def handle(self, *args, **options):
        if len(args) != 3:
            print "Usage: python manage.py send_stats [incr|decr|timing|timer|gauge] name val"
            exit(1)

        operation = args[0]
        name = args[1]
        val = args[2]

        if settings.USING_STATSD:
            from statsd import statsd

            func = getattr(statsd, operation)
            func(name, val)
