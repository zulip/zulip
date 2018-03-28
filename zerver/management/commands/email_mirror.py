
"""
Forward messages sent to the configured email gateway to Zulip.

For zulip.com, messages to that address go to the Inbox of emailgateway@zulip.com.
Zulip voyager configurations will differ.

Messages meant for Zulip have a special recipient form of

    <stream name>+<regenerable stream token>@streams.zulip.com

This pattern is configurable via the EMAIL_GATEWAY_PATTERN settings.py
variable.

Run this in a cronjob every N minutes if you have configured Zulip to poll
an external IMAP mailbox for messages. The script will then connect to
your IMAP server and batch-process all messages.

We extract and validate the target stream from information in the
recipient address and retrieve, forward, and archive the message.

"""


import email
import logging
from email.message import Message
from imaplib import IMAP4_SSL
from typing import Any, Generator, List

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.email_mirror import logger, process_message

## Setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.EMAIL_MIRROR_LOG_PATH)
file_handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def get_imap_messages() -> Generator[Message, None, None]:
    mbox = IMAP4_SSL(settings.EMAIL_GATEWAY_IMAP_SERVER, settings.EMAIL_GATEWAY_IMAP_PORT)
    mbox.login(settings.EMAIL_GATEWAY_LOGIN, settings.EMAIL_GATEWAY_PASSWORD)
    try:
        mbox.select(settings.EMAIL_GATEWAY_IMAP_FOLDER)
        try:
            status, num_ids_data = mbox.search(None, 'ALL')  # type: ignore # https://github.com/python/typeshed/pull/1762
            for msgid in num_ids_data[0].split():
                status, msg_data = mbox.fetch(msgid, '(RFC822)')
                msg_as_bytes = msg_data[0][1]
                message = email.message_from_bytes(msg_as_bytes)
                yield message
                mbox.store(msgid, '+FLAGS', '\\Deleted')
            mbox.expunge()
        finally:
            mbox.close()
    finally:
        mbox.logout()


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args: Any, **options: str) -> None:
        # We're probably running from cron, try to batch-process mail
        if (not settings.EMAIL_GATEWAY_BOT or not settings.EMAIL_GATEWAY_LOGIN or
            not settings.EMAIL_GATEWAY_PASSWORD or not settings.EMAIL_GATEWAY_IMAP_SERVER or
                not settings.EMAIL_GATEWAY_IMAP_PORT or not settings.EMAIL_GATEWAY_IMAP_FOLDER):
            print("Please configure the Email Mirror Gateway in /etc/zulip/, "
                  "or specify $ORIGINAL_RECIPIENT if piping a single mail.")
            exit(1)
        for message in get_imap_messages():
            process_message(message)
