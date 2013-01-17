from optparse import make_option
from django.core.management.base import BaseCommand
import simplejson
import pika
from zephyr.lib.actions import process_user_activity_event
from zephyr.lib.queue import SimpleQueueClient

class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = "Process UserActivity log messages."

    def handle(self, *args, **options):
        activity_queue = SimpleQueueClient.get_instance()

        def callback(ch, method, properties, event):
            print " [x] Received %r" % (event,)
            process_user_activity_event(event)

        print ' [*] Waiting for messages. To exit press CTRL+C'
        activity_queue.register_json_consumer('user_activity', callback)
        activity_queue.start_consuming()

