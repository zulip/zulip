from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_unless_locked

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import invoice_plans_as_needed


class Command(ZulipBaseCommand):
    help = """Generates invoices for customers if needed."""

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        if settings.BILLING_ENABLED:
            # Uncomment to test with a specific date.
            # from datetime import datetime, timezone
            # date = datetime(2024, 5, 7, tzinfo=timezone.utc)
            invoice_plans_as_needed()
