from typing import Any

from django.conf import settings

from zerver.lib.management import ZulipBaseCommand
if settings.BILLING_ENABLED:
    from corporate.lib.stripe import invoice_plans_as_needed

class Command(ZulipBaseCommand):
    help = """Generates invoices for customers if needed."""

    def handle(self, *args: Any, **options: Any) -> None:
        if settings.BILLING_ENABLED:
            invoice_plans_as_needed()
