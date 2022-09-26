from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser

from zerver.lib.management import ZulipBaseCommand

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import switch_realm_from_standard_to_plus_plan


class Command(ZulipBaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)

        if not realm:
            raise CommandError("No realm found.")

        if settings.BILLING_ENABLED:
            switch_realm_from_standard_to_plus_plan(realm)
