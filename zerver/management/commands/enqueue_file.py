import sys
from argparse import ArgumentParser
from typing import IO, Any

import orjson
from django.core.management.base import BaseCommand

from zerver.lib.queue import queue_json_publish


def error(*args: Any) -> None:
    raise Exception("We cannot enqueue because settings.USING_RABBITMQ is False.")


def enqueue_file(queue_name: str, f: IO[str]) -> None:
    for line in f:
        line = line.strip()
        try:
            payload = line.split("\t")[1]
        except IndexError:
            payload = line

        print(f"Queueing to queue {queue_name}: {payload}")

        # Verify that payload is valid json.
        data = orjson.loads(payload)

        # This is designed to use the `error` method rather than
        # the call_consume_in_tests flow.
        queue_json_publish(queue_name, data, error)


class Command(BaseCommand):
    help = """Read JSON lines from a file and enqueue them to a worker queue.

Each line in the file should either be a JSON payload or two tab-separated
fields, the second of which is a JSON payload.  (The latter is to accommodate
the format of error files written by queue workers that catch exceptions--their
first field is a timestamp that we ignore.)

You can use "-" to represent stdin.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "queue_name", metavar="<queue>", help="name of worker queue to enqueue to"
        )
        parser.add_argument(
            "file_name", metavar="<file>", help="name of file containing JSON lines"
        )

    def handle(self, *args: Any, **options: str) -> None:
        queue_name = options["queue_name"]
        file_name = options["file_name"]

        if file_name == "-":
            enqueue_file(queue_name, sys.stdin)
        else:
            with open(file_name) as f:
                enqueue_file(queue_name, f)
