from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from optparse import make_option
from django.core.management.base import BaseCommand, CommandParser
from zerver.models import get_realm_by_string_id, Message, Realm, Stream, Recipient

import datetime
import time

class Command(BaseCommand):
    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        default_cutoff = time.time() - 60 * 60 * 24 * 30 # 30 days.
        parser.add_argument('--realm',
                            dest='string_id',
                            type=str,
                            help='The subdomain/string_id of realm whose public streams you want to dump.')

        parser.add_argument('--since',
                            dest='since',
                            type=int,
                            default=default_cutoff,
                            help='The time in epoch since from which to start the dump.')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = get_realm_by_string_id(options["string_id"])
        streams = Stream.objects.filter(realm=realm, invite_only=False)
        recipients = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=[stream.id for stream in streams])
        cutoff = datetime.datetime.fromtimestamp(options["since"])
        messages = Message.objects.filter(pub_date__gt=cutoff, recipient__in=recipients)

        for message in messages:
            print(message.to_dict(False))
