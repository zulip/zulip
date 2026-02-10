import argparse
import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F, QuerySet
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
        if options["since"]:
            since_time = timezone_now() - timedelta(hours=options["since"])
            # Two ways the count can change -- via a subscription
            # being changed, or via a user being (de)activated.
            changed_subs = RealmAuditLog.objects.filter(
                event_type__in=(
                    AuditLogEventType.SUBSCRIPTION_CREATED,
                    AuditLogEventType.SUBSCRIPTION_ACTIVATED,
                    AuditLogEventType.SUBSCRIPTION_DEACTIVATED,
                ),
                event_time__gte=since_time,
            )
            if realm:
                changed_subs = changed_subs.filter(realm=realm)

            # Find all users changed in the time period, join those to
            # their subscriptions and distinct recipients, and thence
            # to streams.
            changed_users = RealmAuditLog.objects.filter(
                event_type__in=(
                    AuditLogEventType.USER_CREATED,
                    AuditLogEventType.USER_DEACTIVATED,
                    AuditLogEventType.USER_ACTIVATED,
                    AuditLogEventType.USER_REACTIVATED,
                ),
                event_time__gte=since_time,
            )
            if realm:
                changed_users = changed_users.filter(realm=realm)
            changed_user_ids = (
                changed_users.values_list("modified_user_id", flat=True)
                .distinct()
                .order_by("modified_user_id")
            )

            changed_user_subs = (
                Subscription.objects.filter(user_profile_id__in=changed_user_ids)
                .values_list("recipient_id", flat=True)
                .distinct()
                .order_by("recipient_id")
            )
            streams_from_users = Stream.objects.filter(recipient_id__in=changed_user_subs)
            if realm:
                streams_from_users = streams_from_users.filter(realm=realm)

            stream_ids: QuerySet[Any, int] = (
                changed_subs.distinct("modified_stream_id")
                .order_by("modified_stream_id")
                .annotate(stream_id=F("modified_stream_id"))
                .union(streams_from_users.annotate(stream_id=F("id")))
                .values_list("stream_id", flat=True)
            )
        elif realm := self.get_realm(options):
            stream_ids = streams.filter(realm=realm).values_list("id", flat=True)
        else:
            stream_ids = streams.all().values_list("id", flat=True)

        for stream_id in stream_ids.iterator():
            with transaction.atomic(durable=True):
                stream = Stream.objects.select_for_update().get(id=stream_id)
                actual_subscriber_count = Subscription.objects.filter(
                    active=True,
                    recipient__type=2,
                    recipient__type_id=stream_id,
                    is_user_active=True,
                ).count()
                db_count = stream.subscriber_count
                if actual_subscriber_count == db_count:
                    continue
                stream.subscriber_count = actual_subscriber_count
                stream.save(update_fields=["subscriber_count"])

            logging.info(
                "Updated subscriber count of %s, #%s: from %d to %d",
                stream.realm.string_id,
                stream.name,
                db_count,
                actual_subscriber_count,
            )
