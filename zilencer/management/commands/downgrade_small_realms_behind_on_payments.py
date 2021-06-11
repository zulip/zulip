from typing import Any

from corporate.lib.stripe import downgrade_small_realms_behind_on_payments_as_needed
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = "Downgrade small realms that are running behind on payments"

    def handle(self, *args: Any, **options: Any) -> None:
        downgrade_small_realms_behind_on_payments_as_needed()
