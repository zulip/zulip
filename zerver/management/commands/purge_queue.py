from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.core.management import CommandError
from zerver.lib.queue import SimpleQueueClient

class Command(BaseCommand):
    args = "<queue name>"
    help = "Discards all messages from the given queue"
    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError("Wrong number of arguments")

        queue_name = args[0]
        queue = SimpleQueueClient()
        queue.ensure_queue(queue_name, lambda: None)
        queue.channel.queue_purge(queue_name)
        print "Done"
