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
from zerver.lib.management import sleep_forever
from zerver.models import Recipient, ScheduledMessage, Stream, Message, get_user, \
    UserProfile, get_user_by_delivery_email, get_system_bot, get_huddle_user_ids
from zerver.lib.actions import do_send_messages, internal_send_private_message
from zerver.lib.addressee import Addressee

## Setup ##
logger = logging.getLogger(__name__)
log_to_file(logger, settings.SCHEDULED_MESSAGE_DELIVERER_LOG_PATH)

class Command(BaseCommand):
    help = """Deliver scheduled messages from the ScheduledMessage table.
Run this command under supervisor.

This management command is run via supervisor.  Do not run on multiple
machines, as you may encounter multiple sends in a specific race
condition.  (Alternatively, you can set `EMAIL_DELIVERER_DISABLED=True`
on all but one machine to make the command have no effect.)

Usage: ./manage.py deliver_scheduled_messages
"""

    def should_deliver(self, message: ScheduledMessage) -> bool:
        original_sender = message.sender
        if not original_sender.is_active:
            return False

        def tell_original_sender(error_msg: str) -> None:
            if not original_sender.is_active:
                return

            content = error_msg + (":\n```quote\n%s\n```" % (message.content))
            if message.delivery_type == ScheduledMessage.SEND_LATER:
                content = content % ("scheduled message")
                alert_deliverer = get_system_bot(settings.NOTIFICATION_BOT)
            elif message.delivery_type == ScheduledMessage.REMIND:
                content = content % ("reminder message")
                alert_deliverer = get_user(settings.REMINDER_BOT, original_sender.realm)
            internal_send_private_message(original_sender.realm, alert_deliverer,
                                          original_sender, content)

        recipient = message.recipient
        generic_err_msg = ("Hi there! Just wanted to let you know that we "
                           "could not deliver your %s (quoted below) because ")
        if recipient.type == Recipient.STREAM:
            stream = list(Stream.objects.filter(id=recipient.type_id))[0]
            if stream.deactivated:
                err_msg = generic_err_msg + ("the recipient stream %s "
                                             "was deleted." % (stream.name.split(':')[1]))
                tell_original_sender(err_msg)
                return False
        elif recipient.type == Recipient.PERSONAL:
            recipient_user = list(UserProfile.objects.filter(id=recipient.type_id))[0]
            if not recipient_user.is_active:
                err_msg = generic_err_msg + ("the recipient user %s "
                                             "was deactivated." % (recipient_user.full_name))
                tell_original_sender(err_msg)
                return False
        elif recipient.type == Recipient.HUDDLE:
            huddle_user_ids = get_huddle_user_ids(recipient)
            active_user_ids_count = UserProfile.objects.filter(
                id__in=huddle_user_ids, is_active=True).count()
            if len(huddle_user_ids) != active_user_ids_count:
                err_msg = generic_err_msg + "one or more users in the recipient huddle were deactivated."
                tell_original_sender(err_msg)
                return False
        return True

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
            message.sender = get_user_by_delivery_email(settings.NOTIFICATION_BOT, original_sender.realm)

        return {'message': message, 'stream': scheduled_message.stream,
                'realm': scheduled_message.realm}

    def handle(self, *args: Any, **options: Any) -> None:

        if settings.EMAIL_DELIVERER_DISABLED:
            # Here doing a check and sleeping indefinitely on this setting might
            # not sound right. Actually we do this check to avoid running this
            # process on every server that might be in service to a realm. See
            # the comment in zproject/settings.py file about renaming this setting.
            sleep_forever()

        with lockfile("/tmp/zulip_scheduled_message_deliverer.lockfile"):
            while True:
                messages_to_deliver = ScheduledMessage.objects.filter(
                    scheduled_timestamp__lte=timezone_now(),
                    delivered=False)
                if messages_to_deliver:
                    for message in messages_to_deliver:
                        with transaction.atomic():
                            if self.should_deliver(message):
                                do_send_messages([self.construct_message(message)])
                            message.delivered = True
                            message.save(update_fields=['delivered'])

                cur_time = timezone_now()
                time_next_min = (cur_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
                sleep_time = (time_next_min - cur_time).total_seconds()
                time.sleep(sleep_time)
