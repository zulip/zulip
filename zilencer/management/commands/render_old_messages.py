from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand

from zerver.models import Message
import datetime
import time

class Command(BaseCommand):
    help = """Render all historical messages that haven't been rendered yet.

Usage: python2.7 manage.py render_old_messages"""

    def handle(self, *args, **options):
        total_rendered = 0
        while True:
            messages = Message.objects.filter(rendered_content_version=None)[0:100]
            if len(messages) == 0:
                break
            for message in messages:
                message.maybe_render_content(None, save=True)
            total_rendered += len(messages)
            print(datetime.datetime.now(), total_rendered)
            # Put in some sleep so this can run safely on low resource machines
            time.sleep(0.25)
