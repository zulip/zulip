from datetime import timedelta
from typing import Any

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.models import IdempotentMessage


class Command(ZulipBaseCommand):
    help = """deletes old IdempotentMessage as they're transient metadata, should be run periodically every week."""

    @override
    def handle(self, *args: Any, **options: str) -> None:
        # time one hour ago from now
        HOUR_AGO = timezone_now() - timedelta(hours=1)
        # Don't delete messages sent within the last hour,
        # just in case there was an http replay of the same message within that time window.
        IdempotentMessage.objects.filter(time_sent__lt=HOUR_AGO).delete()
