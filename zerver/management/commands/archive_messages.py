from typing import Any

from typing_extensions import override

from zerver.actions.realm_settings import (
    clean_deactivated_realm_data,
    delete_expired_demo_organizations,
)
from zerver.lib.management import ZulipBaseCommand, abort_unless_locked
from zerver.lib.retention import archive_messages, clean_archived_data


class Command(ZulipBaseCommand):
    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: str) -> None:
        clean_archived_data()
        archive_messages()
        scrub_realms()


def scrub_realms() -> None:
    # First, scrub currently deactivated realms that have an expired
    # scheduled deletion date. Then, deactivate and scrub realms with
    # an expired scheduled demo organization deletion date.
    clean_deactivated_realm_data()
    delete_expired_demo_organizations()
