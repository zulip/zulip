import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.models.messages import Message
from zerver.models.recipients import Recipient
from zerver.models.streams import Stream

## Logging setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)


class Command(ZulipBaseCommand):
    help = """For all streams, update the `is_recently_active` field to False if no message has been sent to the stream in the last 180 days."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        date_180_days_ago = timezone_now() - timedelta(days=1)

        active_stream_ids = (
            Message.objects.filter(
                date_sent__gte=date_180_days_ago, recipient__type=Recipient.STREAM
            )
            .values_list("recipient__type_id", flat=True)
            .distinct()
        )

        streams_to_deactivate = Stream.objects.filter(is_recently_active=True).exclude(
            id__in=active_stream_ids
        )

        count = streams_to_deactivate.update(is_recently_active=False)

        logger.info("Marked %s streams as not recently active.", count)
