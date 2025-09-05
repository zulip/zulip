import argparse
import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.logging_util import log_to_file
from zerver.lib.management import ZulipBaseCommand
from zerver.models import RealmAuditLog, Stream, Subscription
from zerver.models.realm_audit_logs import AuditLogEventType

## Logging setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.DIGEST_LOG_PATH)


class Command(ZulipBaseCommand):
    help = """Update the `Stream.subscriber_count` field based on current subscribers.

There may be race conditions with keeping the cached subscriber count
accurate; this command is run as a daily cron job to ensure the number is accurate.
"""

    @override
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--since",
            type=int,
            help="Only examine channels with changed subscribers in this many hours",
        )
        self.add_realm_args(parser, help="The optional name of the realm to limit to")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        streams = Stream.objects.all()
        if realm := self.get_realm(options):
            stream_ids: QuerySet[Any, int] = streams.filter(realm=realm).values_list(
                "id", flat=True
            )
        if options["since"]:
            changed = RealmAuditLog.objects.filter(
                event_type__in=(
                    AuditLogEventType.SUBSCRIPTION_CREATED,
                    AuditLogEventType.SUBSCRIPTION_ACTIVATED,
                    AuditLogEventType.SUBSCRIPTION_DEACTIVATED,
                ),
                event_time__gte=timezone_now() - timedelta(hours=options["since"]),
            )
            if realm:
                changed = changed.filter(realm=realm)
            stream_ids = (
                changed.values_list("modified_stream_id", flat=True)
                .distinct()
                .order_by("modified_stream_id")
            )
        for stream_id in stream_ids.iterator():
            with transaction.atomic(durable=True):
                stream = Stream.objects.select_for_update().get(id=stream_id)
                actual_subscriber_count = Subscription.objects.filter(
                    active=True,
                    recipient__type=2,
                    recipient__type_id=stream_id,
                    is_user_active=True,
                ).count()
                if actual_subscriber_count == stream.subscriber_count:
                    continue
                stream.subscriber_count = actual_subscriber_count
                stream.save(update_fields=["subscriber_count"])
