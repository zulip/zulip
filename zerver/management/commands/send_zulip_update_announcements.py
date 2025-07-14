from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_cron_during_deploy, abort_unless_locked
from zerver.lib.zulip_update_announcements import send_zulip_update_announcements
from zerver.models import Realm


class Command(ZulipBaseCommand):
    help = """Script to send zulip update announcements to realms."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--skip-delay",
            action="store_true",
            help="Immediately send updates if 'zulip_update_announcements_stream' is configured.",
        )
        parser.add_argument(
            "--reset-level",
            type=int,
            help="The level to reset all active realms to.",
        )

    @override
    @abort_cron_during_deploy
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        if options["reset_level"] is not None:
            Realm.objects.filter(deactivated=False).exclude(
                string_id=settings.SYSTEM_BOT_REALM
            ).update(zulip_update_announcements_level=options["reset_level"])
            return

        send_zulip_update_announcements(skip_delay=options["skip_delay"])
