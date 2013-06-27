from __future__ import absolute_import

from django.core.management.base import BaseCommand
from zephyr.models import StreamColor

class Command(BaseCommand):
    help = """Copies all colors from the StreamColor table to the Subscription table."""

    def handle(self, *args, **options):
        for stream_color in StreamColor.objects.all():
            subscription = stream_color.subscription
            subscription.color = stream_color.color
            subscription.save(update_fields=["color"])
