#!/usr/bin/python

"""
Forward messages sent to the configured email gateway to Zulip.

Messages to that address go to the Inbox of emailgateway@zulip.com.

Messages meant for Zulip have a special recipient form of

<stream name>+<regenerable stream token>@streams.zulip.com

We extract and validate the target stream from information in the
recipient address and retrieve, forward, and archive the message.

Run this management command out of a cron job.
"""

from __future__ import absolute_import

import email
import os
from email.header import decode_header
import logging
import re
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.actions import decode_email_address, convert_html_to_markdown
from zerver.lib.upload import upload_message_image
from zerver.models import Stream, get_user_profile_by_email, UserProfile
from zerver.lib.email_mirror import logger, process_message

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
    help = """Forward emails sent to the configured email gateway to Zulip.

Run this command out of a cron job.
"""

    def handle(self, **options):
        if (not settings.EMAIL_GATEWAY_BOT or not settings.EMAIL_GATEWAY_LOGIN or
            not settings.EMAIL_GATEWAY_PASSWORD or not settings.EMAIL_GATEWAY_IMAP_SERVER or
            not settings.EMAIL_GATEWAY_IMAP_PORT or not settings.EMAIL_GATEWAY_IMAP_FOLDER):
            print "Please configure the Email Mirror Gateway in your local_settings.py"
            exit(1)

        reactor.callLater(0, main)
        reactor.run()
