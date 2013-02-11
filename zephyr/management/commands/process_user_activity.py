from optparse import make_option
from django.core.management.base import BaseCommand
import simplejson
import pika
from zephyr.lib.actions import process_user_activity_event, process_user_presence_event
from zephyr.lib.queue import SimpleQueueClient

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Process UserActivity & UserPresence log messages."

    def handle(self, *args, **options):
        activity_queue = SimpleQueueClient()

        def callback_activity(ch, method, properties, event):
            print " [x] Received activity %r" % (event,)
            process_user_activity_event(event)

        def callback_presence(ch, method, properties, event):
            print " [x] Received presence %r" % (event,)
            process_user_presence_event(event)

        print ' [*] Waiting for messages. To exit press CTRL+C'
        activity_queue.register_json_consumer('user_activity', callback_activity)
        activity_queue.register_json_consumer('user_presence', callback_presence)
        activity_queue.start_consuming()

