from __future__ import absolute_import

from django.core.management.base import BaseCommand
from zerver.lib.queue import queue_json_publish

import sys
import ujson


def error(*args):
    raise Exception('We cannot enqueue because settings.USING_RABBITMQ is False.')

class Command(BaseCommand):
    help = """Read JSON lines from a file and enqueue them to a worker queue.

Each line in the file should either be a JSON payload or two tab-separated
fields, the second of which is a JSON payload.  (The latter is to accomodate
the format of error files written by queue workers that catch exceptions--their
first field is a timestamp that we ignore.)

Usage: python manage.py enqueue_file <queue_name> <file_name>

You can use "-" to represent stdin.
"""

    def handle(self, *args, **options):
        if len(args) != 2:
            print "Please provide a queue and file name."
            exit(1)

        queue_name, file_name = args

        if file_name == '-':
            f = sys.stdin
        else:
            f = open(file_name)

        while True:
            line = f.readline()
            if not line:
                break

            line = line.strip()
            try:
                payload = line.split('\t')[1]
            except IndexError:
                payload = line

            print 'Queueing to queue %s: %s' % (queue_name, payload)

            # Verify that payload is valid json.
            data = ujson.loads(payload)

            queue_json_publish(queue_name, data, error)
