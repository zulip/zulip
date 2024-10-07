import logging
from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import check_update_all_streams_active_status

## Logging setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)


class Command(ZulipBaseCommand):
    help = """Update the `Stream.is_recently_active` field to False for channels whose message history has aged to the point where it is no longer recently active."""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        count = check_update_all_streams_active_status()
        logger.info("Marked %s channels as not recently active.", count)
