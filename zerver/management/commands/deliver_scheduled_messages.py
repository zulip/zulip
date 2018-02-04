import logging
import time
from typing import Any, Dict
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.context_managers import lockfile
from zerver.lib.logging_util import log_to_file
from zerver.models import ScheduledMessage, Message, get_user
from zerver.lib.actions import do_send_messages
from zerver.lib.addressee import Addressee

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.SCHEDULED_MESSAGE_DELIVERER_LOG_PATH)

class Command(BaseCommand):
    help = """Deliver scheduled messages from the ScheduledMessage table.
Run this command under supervisor.

Usage: ./manage.py deliver_scheduled_messages
"""

    def construct_message(self, scheduled_message: ScheduledMessage) -> Dict[str, Any]:
        message = Message()
        original_sender = scheduled_message.sender
        message.content = scheduled_message.content
        message.recipient = scheduled_message.recipient
        message.subject = scheduled_message.subject
        message.pub_date = timezone_now()
        message.sending_client = scheduled_message.sending_client

        delivery_type = scheduled_message.delivery_type
        if delivery_type == ScheduledMessage.SEND_LATER:
            message.sender = original_sender
        elif delivery_type == ScheduledMessage.REMIND:
            message.sender = get_user(settings.REMINDER_BOT, original_sender.realm)
            whos_reminding = ('%s asked me to do a reminder about:\n' % (original_sender.full_name))
            message.content = whos_reminding + message.content

        return {'message': message, 'stream': scheduled_message.stream,
                'realm': scheduled_message.realm}

    def handle(self, *args: Any, **options: Any) -> None:
        with lockfile("/tmp/zulip_scheduled_message_deliverer.lockfile"):
            while True:
                messages_to_deliver = ScheduledMessage.objects.filter(
                    scheduled_timestamp__lte=timezone_now(),
                    delivered=False)
                if messages_to_deliver:
                    for message in messages_to_deliver:
                        with transaction.atomic():
                            do_send_messages([self.construct_message(message)])
                            message.delivered = True
                            message.save(update_fields=['delivered'])

                cur_time = timezone_now()
                time_next_min = (cur_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_time = (time_next_min - cur_time).total_seconds()
                time.sleep(sleep_time)
