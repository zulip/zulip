from typing import Any

from django.core.management.base import CommandParser

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.message import maybe_update_first_visible_message_id
from zerver.models import Realm


class Command(ZulipBaseCommand):
    help = """Calculate the value of first visible message ID and store it in cache"""

    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser)
        parser.add_argument(
            '--lookback-hours',
            dest='lookback_hours',
            type=int,
            help="Period a bit larger than that of the cron job that runs "
                 "this command so that the lookback periods are sure to overlap.",
            required=True,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)

        if realm is None:
            realms = Realm.objects.all()
        else:
            realms = [realm]

        for realm in realms:
            maybe_update_first_visible_message_id(realm, options['lookback_hours'])
