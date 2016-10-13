from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from optparse import make_option
from django.core.management.base import BaseCommand
from zerver.models import get_realm, Message, Realm, Stream, Recipient

import datetime
import time

class Command(BaseCommand):
    default_cutoff = time.time() - 60 * 60 * 24 * 30 # 30 days.

    option_list = BaseCommand.option_list + (
        make_option('--domain',
                    dest='domain',
                    type='str',
                    help='The domain whose public streams you want to dump.'),
        make_option('--since',
                    dest='since',
                    type='int',
                    default=default_cutoff,
                    help='The time in epoch since from which to start the dump.')
        )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = get_realm(options["domain"])
        streams = Stream.objects.filter(realm=realm, invite_only=False)
        recipients = Recipient.objects.filter(
            type=Recipient.STREAM, type_id__in=[stream.id for stream in streams])
        cutoff = datetime.datetime.fromtimestamp(options["since"])
        messages = Message.objects.filter(pub_date__gt=cutoff, recipient__in=recipients)

        for message in messages:
            print(message.to_dict(False))
