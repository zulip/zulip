from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from django.core.management.base import BaseCommand

import zerver.lib.bugdown as bugdown
from zerver.lib.message import re_render_content_for_management_command
from zerver.models import Message
import datetime
import time

class Command(BaseCommand):
    help = """Render all historical messages that haven't been rendered yet.

Usage: python manage.py render_old_messages"""

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        total_rendered = 0
        while True:
            messages = Message.objects.exclude(rendered_content_version=bugdown.version)[0:100]
            if len(messages) == 0:
                break
            for message in messages:
                re_render_content_for_management_command(message)
            total_rendered += len(messages)
            print(datetime.datetime.now(), total_rendered)
            # Put in some sleep so this can run safely on low resource machines
            time.sleep(0.25)
