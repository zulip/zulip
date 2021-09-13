"""Cron job implementation of Zulip's incoming email gateway's helper
for forwarding emails into Zulip.

https://zulip.readthedocs.io/en/latest/production/email-gateway.html

The email gateway supports two major modes of operation: An email
server where the email address configured in EMAIL_GATEWAY_PATTERN
delivers emails directly to Zulip, and this, a cron job that connects
to an IMAP inbox (which receives the emails) periodically.

Run this in a cron job every N minutes if you have configured Zulip to
poll an external IMAP mailbox for messages. The script will then
connect to your IMAP server and batch-process all messages.

We extract and validate the target stream from information in the
recipient address and retrieve, forward, and archive the message.

"""

import email.parser
import email.policy
import logging
from collections.abc import Generator
from email.message import EmailMessage
from imaplib import IMAP4_SSL
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError
from typing_extensions import override

from zerver.lib.email_mirror import logger, process_message
from zerver.lib.management import ZulipBaseCommand

## Setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.EMAIL_MIRROR_LOG_PATH)
file_handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def get_imap_messages() -> Generator[EmailMessage, None, None]:
    # We're probably running from cron, try to batch-process mail
    if (
        not settings.EMAIL_GATEWAY_BOT
        or not settings.EMAIL_GATEWAY_LOGIN
        or not settings.EMAIL_GATEWAY_PASSWORD
        or not settings.EMAIL_GATEWAY_IMAP_SERVER
        or not settings.EMAIL_GATEWAY_IMAP_PORT
        or not settings.EMAIL_GATEWAY_IMAP_FOLDER
    ):
        raise CommandError(
            "Please configure the email mirror gateway in /etc/zulip/, "
            "or specify $ORIGINAL_RECIPIENT if piping a single mail."
        )
    mbox = IMAP4_SSL(settings.EMAIL_GATEWAY_IMAP_SERVER, settings.EMAIL_GATEWAY_IMAP_PORT)
    mbox.login(settings.EMAIL_GATEWAY_LOGIN, settings.EMAIL_GATEWAY_PASSWORD)
    try:
        mbox.select(settings.EMAIL_GATEWAY_IMAP_FOLDER)
        try:
            status, num_ids_data = mbox.search(None, "ALL")
            for message_id in num_ids_data[0].split():
                status, msg_data = mbox.fetch(message_id, "(RFC822)")
                assert isinstance(msg_data[0], tuple)
                msg_as_bytes = msg_data[0][1]
                yield email.parser.BytesParser(
                    _class=EmailMessage, policy=email.policy.default
                ).parsebytes(msg_as_bytes)
                mbox.store(message_id, "+FLAGS", "\\Deleted")
            mbox.expunge()
        finally:
            mbox.close()
    finally:
        mbox.logout()


class Command(ZulipBaseCommand):
    help = __doc__

    @override
    def handle(self, *args: Any, **options: str) -> None:
        for message in get_imap_messages():
            process_message(message)
