from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import RealmBillingSession
    from corporate.models.plans import CustomerPlan


class Command(ZulipBaseCommand):
    @override
    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)

        if not realm:
            raise CommandError("No realm found.")

        if settings.BILLING_ENABLED:
            billing_session = RealmBillingSession(realm=realm)
            billing_session.do_change_plan_to_new_tier(new_plan_tier=CustomerPlan.TIER_CLOUD_PLUS)
