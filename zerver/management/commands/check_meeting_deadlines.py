from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.meeting_actions import check_meeting_deadlines


class Command(ZulipBaseCommand):
    help = """Mark proposed meetings whose RSVP deadline has passed and notify owners.

Intended to be run periodically (e.g. cron). Usage: ./manage.py check_meeting_deadlines
"""

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        check_meeting_deadlines()
