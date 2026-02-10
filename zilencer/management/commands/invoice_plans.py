import datetime
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_unless_locked

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import invoice_plans_as_needed


class Command(ZulipBaseCommand):
    help = """Generates invoices for customers if needed."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        if settings.DEVELOPMENT:
            parser.add_argument("--date", type=datetime.datetime.fromisoformat)

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.BILLING_ENABLED:
            raise CommandError("Billing is not enabled!")

        for_date = None
        if settings.DEVELOPMENT and options["date"]:
            for_date = options["date"].replace(tzinfo=datetime.timezone.utc)

        invoice_plans_as_needed(for_date)
