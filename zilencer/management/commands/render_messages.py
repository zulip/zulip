from __future__ import absolute_import
from __future__ import print_function

import os
import datetime
from typing import Any, Generator

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import QuerySet

from zerver.lib.message import render_markdown
from zerver.lib.str_utils import force_str
from zerver.models import Message


def queryset_iterator(queryset, chunksize=100):
    # type: (QuerySet, int) -> Generator
    if queryset.count():
        queryset = queryset.order_by('pk')
        while queryset.count():
            for row in queryset[:chunksize]:
                pk = row.pk
                yield row
            queryset = queryset.filter(pk__gt=pk)


class Command(BaseCommand):
    help = """
    Render messages to a file.
    Usage: python manage.py render_messages <destination> <--amount>
    """

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('destination', help='Destination folder for resulting file')
        parser.add_argument('--amount', default=100000, required=False, help='Amount of messages')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        dest_dir = options['destination']
        amount = options['amount']
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        now = datetime.datetime.now()
        with open(os.path.join(dest_dir, now.strftime('%Y-%m-%d-%H:%M:%S.txt')), 'w') as result:
            latest = Message.objects.latest('pub_date').id
            messages = Message.objects.filter(pk__gt=latest-amount).order_by('pk')
            for message in queryset_iterator(messages):
                result.write(force_str(render_markdown(message, message.content)))
