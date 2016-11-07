from __future__ import absolute_import
from __future__ import print_function

import os
import json
from typing import Any, Generator

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import QuerySet

from zerver.lib.message import render_markdown
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
        parser.add_argument('destination', help='Destination file path')
        parser.add_argument('--amount', default=100000, help='Amount of messages')
        parser.add_argument('--latest_id', default=0, help="Last message id")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        dest_dir = os.path.realpath(os.path.dirname(options['destination']))
        amount = int(options['amount'])
        latest = int(options['latest_id']) or Message.objects.latest('id').id
        self.stdout.write('Latest message id: {latest}'.format(latest=latest))
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        with open(options['destination'], 'w') as result:
            result.write('[')
            messages = Message.objects.filter(pk__gt=latest - amount, pk__lte=latest).order_by('pk')
            for message in queryset_iterator(messages):
                result.write(json.dumps({
                    'id': message.id,
                    'content': render_markdown(message, message.content)
                }))
                if message.id != latest:
                    result.write(',')
            result.write(']')
