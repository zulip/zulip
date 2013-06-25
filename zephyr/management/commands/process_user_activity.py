from __future__ import absolute_import

from optparse import make_option
from django.core.management.base import BaseCommand
import ujson
import pika
from zephyr.lib.actions import process_user_activity_event, \
        process_user_presence_event
from zephyr.lib.queue import SimpleQueueClient
import sys
import signal

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Process UserActivity log messages."

    def handle(self, *args, **options):
        activity_queue = SimpleQueueClient()

        def callback_activity(ch, method, properties, event):
            print " [x] Received activity %r" % (event,)
            msg_type = event['type']
            if msg_type == 'user_activity':
                process_user_activity_event(event)
            elif msg_type == 'user_presence':
                process_user_presence_event(event)
            else:
                print("[*] Unknown message type: %s" (msg_type,))

        def signal_handler(signal, frame):
            print("[*] Closing and disconnecting from queues")
            activity_queue.stop_consuming()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        print ' [*] Waiting for messages. To exit press CTRL+C'
        activity_queue.register_json_consumer('user_activity', callback_activity)
        activity_queue.start_consuming()
