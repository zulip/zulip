#!/usr/bin/python

"""
Forward messages sent to the configured email gateway to Zulip.

At Zulip, messages to that address go to the Inbox of emailgateway@zulip.com.
Zulip enterprise customers' configurations will differ.

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
         |/usr/bin/python /home/zulip/deployments/current/manage.py email-mirror
"""


from __future__ import absolute_import

import email
import os
from email.header import decode_header
import logging
import re
import sys
import posix

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.actions import decode_email_address
from zerver.lib.notifications import convert_html_to_markdown
from zerver.lib.upload import upload_message_image
from zerver.lib.queue import queue_json_publish
from zerver.models import Stream, get_user_profile_by_email, UserProfile
from zerver.lib.email_mirror import logger, process_message, \
    extract_and_validate, ZulipEmailForwardError, \
    mark_missed_message_address_as_used, is_missed_message_address

from twisted.internet import protocol, reactor, ssl
from twisted.mail import imap4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../api"))
import zulip

## Setup ##

log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.EMAIL_MIRROR_LOG_PATH)
file_handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

## IMAP callbacks ##

def logout(result, proto):
    # Log out.
    return proto.logout()

def delete(result, proto):
    # Close the connection, which also processes any flags that were
    # set on messages.
    return proto.close().addCallback(logout, proto)

def fetch(result, proto, mailboxes):
    if not result:
        return proto.logout()

    message_uids = result.keys()
    # Make sure we forward the messages in time-order.
    message_uids.sort()
    for uid in message_uids:
        message = email.message_from_string(result[uid]["RFC822"])
        process_message(message)
    # Delete the processed messages from the Inbox.
    message_set = ",".join([result[key]["UID"] for key in message_uids])
    d = proto.addFlags(message_set, ["\\Deleted"], uid=True, silent=False)
    d.addCallback(delete, proto)

    return d

def examine_mailbox(result, proto, mailbox):
    # Fetch messages from a particular mailbox.
    return proto.fetchMessage("1:*", uid=True).addCallback(fetch, proto, mailbox)

def select_mailbox(result, proto):
    # Select which mailbox we care about.
    mbox = filter(lambda x: settings.EMAIL_GATEWAY_IMAP_FOLDER in x[2], result)[0][2]
    return proto.select(mbox).addCallback(examine_mailbox, proto, result)

def list_mailboxes(res, proto):
    # List all of the mailboxes for this account.
    return proto.list("","*").addCallback(select_mailbox, proto)

def connected(proto):
    d = proto.login(settings.EMAIL_GATEWAY_LOGIN, settings.EMAIL_GATEWAY_PASSWORD)
    d.addCallback(list_mailboxes, proto)
    d.addErrback(login_failed)
    return d

def login_failed(failure):
    return failure

def done(_):
    reactor.callLater(0, reactor.stop)

def main():
    imap_client = protocol.ClientCreator(reactor, imap4.IMAP4Client)
    d = imap_client.connectSSL(settings.EMAIL_GATEWAY_IMAP_SERVER, settings.EMAIL_GATEWAY_IMAP_PORT, ssl.ClientContextFactory())
    d.addCallbacks(connected, login_failed)
    d.addBoth(done)

class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        rcpt_to = os.environ.get("ORIGINAL_RECIPIENT", args[0] if len(args) else None)
        if rcpt_to is not None:
            if is_missed_message_address(rcpt_to):
                try:
                    mark_missed_message_address_as_used(rcpt_to)
                except ZulipEmailForwardError:
                    print "5.1.1 Bad destination mailbox address: Bad or expired missed message address."
                    exit(posix.EX_NOUSER)
            else:
                try:
                    extract_and_validate(rcpt_to)
                except ZulipEmailForwardError:
                    print "5.1.1 Bad destination mailbox address: Please use the address specified in your Streams page."
                    exit(posix.EX_NOUSER)

            # Read in the message, at most 25MiB. This is the limit enforced by
            # Gmail, which we use here as a decent metric.
            message = sys.stdin.read(25*1024*1024)

            if len(sys.stdin.read(1)) != 0:
                # We're not at EOF, reject large mail.
                print "5.3.4 Message too big for system: Max size is 25MiB"
                exit(posix.EX_DATAERR)

            queue_json_publish(
                    "email_mirror",
                    {
                        "message": message,
                        "rcpt_to": rcpt_to
                    },
                    lambda x: None
            )
        else:
            # We're probably running from cron, try to batch-process mail
            if (not settings.EMAIL_GATEWAY_BOT or not settings.EMAIL_GATEWAY_LOGIN or
                not settings.EMAIL_GATEWAY_PASSWORD or not settings.EMAIL_GATEWAY_IMAP_SERVER or
                not settings.EMAIL_GATEWAY_IMAP_PORT or not settings.EMAIL_GATEWAY_IMAP_FOLDER):
                print "Please configure the Email Mirror Gateway in your local_settings.py, or specify $ORIGINAL_RECIPIENT if piping a single mail."
                exit(1)
            reactor.callLater(0, main)
            reactor.run()
