from argparse import ArgumentParser
from typing import Any

from django.core.management import CommandError
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.queue import SimpleQueueClient
from zerver.worker.queue_processors import get_active_worker_queues


class Command(ZulipBaseCommand):
    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(dest="queue_name", nargs="?", help="queue to purge")
        parser.add_argument("--all", action="store_true", help="purge all queues")

    help = "Discards all messages from the given queue"

    @override
    def handle(self, *args: Any, **options: str) -> None:
        def purge_queue(queue_name: str) -> None:
            queue = SimpleQueueClient()
            queue.ensure_queue(queue_name, lambda channel: channel.queue_purge(queue_name))

        if options["all"]:
            for queue_name in get_active_worker_queues():
                purge_queue(queue_name)
            print("All queues purged")
        elif not options["queue_name"]:
            raise CommandError("Missing queue_name argument!")
        else:
            queue_name = options["queue_name"]
            if not (
                queue_name in get_active_worker_queues() or queue_name.startswith("notify_tornado")
            ):
                raise CommandError(f"Unknown queue {queue_name}")

            print(f"Purging queue {queue_name}")
            purge_queue(queue_name)

        print("Done")
