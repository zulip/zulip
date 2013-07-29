from __future__ import absolute_import

from django.conf import settings
from django.core.management.base import BaseCommand
from zerver.lib.actions import process_user_activity_event, \
        process_user_presence_event
from zerver.lib.queue import SimpleQueueClient
import sys
import signal
import os
import traceback
import ujson

ERROR_LOG_FILE = os.path.join(settings.ERROR_LOG_DIR, "process_user_activity")

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Process UserActivity log messages."

    def handle(self, *args, **options):
        activity_queue = SimpleQueueClient()

        def callback_activity(ch, method, properties, event):
            print " [x] Received activity %r" % (event,)
            try:
                process_event(event)
            except Exception:
                if not os.path.exists(settings.ERROR_LOG_DIR):
                    os.mkdir(settings.ERROR_LOG_DIR)
                # One can parse out just the JSON records from this log format using:
                #
                # grep "Error Processing" errors/process_user_activity  | cut -f 2- -d:
                file(ERROR_LOG_FILE, "a").write(
                    "Error Processing event: " + ujson.dumps(event) + "\n" +
                    traceback.format_exc())

        def process_event(event):
            msg_type = event['type']
            if msg_type == 'user_activity':
                process_user_activity_event(event)
            elif msg_type == 'user_presence':
                process_user_presence_event(event)
            else:
                print("[*] Unknown message type: %s" % (msg_type,))

        def signal_handler(signal, frame):
            print("[*] Closing and disconnecting from queues")
            activity_queue.stop_consuming()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        print ' [*] Waiting for messages. To exit press CTRL+C'
        activity_queue.register_json_consumer('user_activity', callback_activity)
        activity_queue.start_consuming()
