#!/usr/bin/env python

"""
Forward messages sent to the configured email gateway to Zulip.

For zulip.com, messages to that address go to the Inbox of emailgateway@zulip.com.
Zulip voyager configurations will differ.

Messages meant for Zulip have a special recipient form of

    <stream name>+<regenerable stream token>@streams.zulip.com

This pattern is configurable via the EMAIL_GATEWAY_PATTERN settings.py
variable.

This script can be used via two mechanisms:

  1) Run this in a cronjob every N minutes if you have configured Zulip to poll
     an external IMAP mailbox for messages. The script will then connect to
     your IMAP server and batch-process all messages.

     We extract and validate the target stream from information in the
     recipient address and retrieve, forward, and archive the message.

  2) Alternatively, configure your MTA to execute this script on message
     receipt with the contents of the message piped to standard input. The
     script will queue the message for processing. In this mode of invocation,
     you should pass the destination email address in the ORIGINAL_RECIPIENT
     environment variable.

     In Postfix, you can express that via an /etc/aliases entry like this:
         |/usr/bin/env python /home/zulip/deployments/current/manage.py email_mirror
"""


from __future__ import absolute_import
from __future__ import print_function

import six
from typing import Any, List, Generator

from argparse import ArgumentParser
import os
import logging
import sys
import posix

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.queue import queue_json_publish
from zerver.lib.email_mirror import logger, process_message, \
    extract_and_validate, ZulipEmailForwardError, \
    mark_missed_message_address_as_used, is_missed_message_address

import email
from email.message import Message
from imaplib import IMAP4_SSL

## Setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.EMAIL_MIRROR_LOG_PATH)
file_handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

def get_imap_messages():
    # type: () -> Generator[Message, None, None]
    mbox = IMAP4_SSL(settings.EMAIL_GATEWAY_IMAP_SERVER, settings.EMAIL_GATEWAY_IMAP_PORT)
    mbox.login(settings.EMAIL_GATEWAY_LOGIN, settings.EMAIL_GATEWAY_PASSWORD)
    try:
        mbox.select(settings.EMAIL_GATEWAY_IMAP_FOLDER)
        try:
            status, num_ids_data = mbox.search(None, 'ALL') # type: bytes, List[bytes]
            for msgid in num_ids_data[0].split():
                status, msg_data = mbox.fetch(msgid, '(RFC822)')
                msg_as_bytes = msg_data[0][1]
                if six.PY2:
                    message = email.message_from_string(msg_as_bytes)
                else:
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

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('recipient', metavar='<recipient>', type=str, nargs='?', default=None,
                            help="original recipient")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        rcpt_to = os.environ.get("ORIGINAL_RECIPIENT", options['recipient'])
        if rcpt_to is not None:
            if is_missed_message_address(rcpt_to):
                try:
                    mark_missed_message_address_as_used(rcpt_to)
                except ZulipEmailForwardError:
                    print("5.1.1 Bad destination mailbox address: Bad or expired missed message address.")
                    exit(posix.EX_NOUSER) # type: ignore # There are no stubs for posix in python 3
            else:
                try:
                    extract_and_validate(rcpt_to)
                except ZulipEmailForwardError:
                    print("5.1.1 Bad destination mailbox address: Please use the address specified "
                          "in your Streams page.")
                    exit(posix.EX_NOUSER) # type: ignore # There are no stubs for posix in python 3

            # Read in the message, at most 25MiB. This is the limit enforced by
            # Gmail, which we use here as a decent metric.
            msg_text = sys.stdin.read(25*1024*1024)

            if len(sys.stdin.read(1)) != 0:
                # We're not at EOF, reject large mail.
                print("5.3.4 Message too big for system: Max size is 25MiB")
                exit(posix.EX_DATAERR) # type: ignore # There are no stubs for posix in python 3

            queue_json_publish(
                    "email_mirror",
                    {
                        "message": msg_text,
                        "rcpt_to": rcpt_to
                    },
                    lambda x: None
            )
        else:
            # We're probably running from cron, try to batch-process mail
            if (not settings.EMAIL_GATEWAY_BOT or not settings.EMAIL_GATEWAY_LOGIN or
                not settings.EMAIL_GATEWAY_PASSWORD or not settings.EMAIL_GATEWAY_IMAP_SERVER or
                not settings.EMAIL_GATEWAY_IMAP_PORT or not settings.EMAIL_GATEWAY_IMAP_FOLDER):
                print("Please configure the Email Mirror Gateway in /etc/zulip/, "
                      "or specify $ORIGINAL_RECIPIENT if piping a single mail.")
                exit(1)
            for message in get_imap_messages():
                process_message(message)
