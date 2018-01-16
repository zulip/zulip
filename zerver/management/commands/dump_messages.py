
import datetime
import time
from typing import Any

from django.core.management.base import CommandParser
from django.utils.timezone import utc as timezone_utc

from zerver.lib.management import ZulipBaseCommand
from zerver.models import Message, Recipient, Stream

class Command(ZulipBaseCommand):
    help = "Dump messages from public streams of a realm"

    def add_arguments(self, parser: CommandParser) -> None:
        default_cutoff = time.time() - 60 * 60 * 24 * 30  # 30 days.
        self.add_realm_args(parser, True)
        parser.add_argument('--since',
                            dest='since',
                            type=int,
                            default=default_cutoff,
                            help='The time in epoch since from which to start the dump.')

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        streams = Stream.objects.filter(realm=realm, invite_only=False)
        recipients = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=[stream.id for stream in streams])
        cutoff = datetime.datetime.fromtimestamp(options["since"], tz=timezone_utc)
        messages = Message.objects.filter(pub_date__gt=cutoff, recipient__in=recipients)

        for message in messages:
            print(message.to_dict(False))
