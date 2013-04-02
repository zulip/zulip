import simplejson
from postmonkey import PostMonkey
from django.core.management.base import BaseCommand
from django.conf import settings

from zephyr.lib.queue import SimpleQueueClient

class Command(BaseCommand):
    pm = PostMonkey(settings.MAILCHIMP_API_KEY, timeout=10)

    def subscribe(self, ch, method, properties, data):
        self.pm.listSubscribe(
                id=settings.HUMBUG_FRIENDS_LIST_ID,
                email_address=data['EMAIL'],
                merge_vars=data['merge_vars'],
                double_optin=False,
                send_welcome=False)

    def handle(self, *args, **options):
        q = SimpleQueueClient()
        q.register_json_consumer("signups", self.subscribe)
        q.start_consuming()
