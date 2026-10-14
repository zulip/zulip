from typing import Any

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_unless_locked
from zerver.models import IdempotentRequest

BATCH_SIZE = 10000


class Command(ZulipBaseCommand):
    help = "Delete IdempotentRequest rows older than IdempotentRequest.RETENTION_PERIOD."

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        expired_requests = IdempotentRequest.objects.filter(
            timestamp__lt=timezone_now() - IdempotentRequest.RETENTION_PERIOD
        )
        deleted_count = 0
        while True:
            batch_deleted_count, _ = IdempotentRequest.objects.filter(
                id__in=expired_requests.values("id")[:BATCH_SIZE]
            ).delete()
            if batch_deleted_count == 0:
                break
            deleted_count += batch_deleted_count
        print(f"Deleted {deleted_count} expired idempotent requests.")
