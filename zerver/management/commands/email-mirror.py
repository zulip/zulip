#!/usr/bin/python

"""
Forward messages sent to @streams.zulip.com to Zulip.

Messages to that address go to the Inbox of emailgateway@zulip.com.

Messages meant for Zulip have a special recipient form of

<stream name>+<regenerable stream token>@streams.zulip.com

We extract and validate the target stream from information in the
recipient address and retrieve, forward, and archive the message.

Run this management command out of a cron job.
"""

import email
from os import path
from email.header import decode_header
import logging
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.actions import decode_email_address
from zerver.models import Stream, get_user_profile_by_email

from twisted.internet import protocol, reactor, ssl
from twisted.mail import imap4

sys.path.insert(0, path.join(path.dirname(__file__), "../../../api"))
import zulip

GATEWAY_EMAIL = "emailgateway@zulip.com"
# Application-specific password.
PASSWORD = "xxxxxxxxxxxxxxxx"

SERVER = "imap.gmail.com"
PORT = 993

## Setup ##

log_file = "/var/log/humbug/email-mirror.log"
log_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

api_key = get_user_profile_by_email(GATEWAY_EMAIL).api_key
if settings.DEPLOYED:
    staging_client = zulip.Client(
        site="https://staging.zulip.com", email=GATEWAY_EMAIL, api_key=api_key)
    prod_client = zulip.Client(
        site="https://api.zulip.com", email=GATEWAY_EMAIL, api_key=api_key)
else:
    staging_client = prod_client = zulip.Client(
        site="http://localhost:9991/api", email=GATEWAY_EMAIL, api_key=api_key)

def log_and_raise(error_msg):
    logger.error(error_msg)
    raise ZulipEmailForwardError(error_msg)

## Sending the Zulip ##

class ZulipEmailForwardError(Exception):
    pass

def send_zulip(stream, topic, content):
    if stream.realm.domain == "zulip.com":
        api_client = staging_client
    else:
        api_client = prod_client

    # TODO: restrictions on who can send? Consider: cross-realm
    # messages, private streams.
    message_data = {
        "type": "stream",
        # TODO: handle rich formatting.
        "content": content[:2000],
        "subject": topic[:60],
        "to": stream.name,
        "domain": stream.realm.domain
        }

    response = api_client.send_message(message_data)
    if response["result"] != "success":
        log_and_raise(response["msg"])

def valid_stream(stream_name, token):
    try:
        stream = Stream.objects.get(email_token=token)
        return stream.name.lower() == stream_name.lower()
    except Stream.DoesNotExist:
        return False

def extract_body(message):
    # "Richly formatted" email are multi-part messages that include a
    # plaintext version of the body. We only want to forward that
    # plaintext version.
    body = None
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True)
    if not body:
        raise ZulipEmailForwardError("Unable to find plaintext message body")

def extract_and_validate(email):
    # Recipient is of the form
    # <stream name>+<regenerable stream token>@streams.zulip.com
    try:
        stream_name_and_token = decode_email_address(email).rsplit("@", 1)[0]
        stream_name, token = stream_name_and_token.rsplit("+", 1)
    except ValueError:
        log_and_raise("Malformed email recipient " + email)

    if not valid_stream(stream_name, token):
        log_and_raise("Bad stream token from email recipient " + email)

    return Stream.objects.get(email_token=token)

## IMAP callbacks ##

def logout(result, proto):
    # Log out.
    return proto.logout()

def delete(result, proto):
    # Close the connection, which also processes any flags that were
    # set on messages.
    return proto.close().addCallback(logout, proto)

def find_emailgateway_recipient(message):
    # We can't use Delivered-To; that is emailgateway@zulip.com.
    for header in ("To", "Cc", "Bcc"):
        recipient = message.get(header)
        if recipient and recipient.lower().endswith("@streams.zulip.com"):
            return recipient
    raise ZulipEmailForwardError("Missing recipient @streams.zulip.com")

def fetch(result, proto, mailboxes):
    if not result:
        return proto.logout()

    message_uids = result.keys()
    # Make sure we forward the messages in time-order.
    message_uids.sort()
    for uid in message_uids:
        message = email.message_from_string(result[uid]["RFC822"])
        subject = decode_header(message.get("Subject", "(no subject)"))[0][0]

        try:
            body = extract_body(message)
            to = find_emailgateway_recipient(message)
            stream = extract_and_validate(to)
            send_zulip(stream, subject, body)
        except ZulipEmailForwardError:
            # TODO: notify sender of error, retry if appropriate.
            pass

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
    mbox = filter(lambda x: "INBOX" in x[2], result)[0][2]
    return proto.select(mbox).addCallback(examine_mailbox, proto, result)

def list_mailboxes(res, proto):
    # List all of the mailboxes for this account.
    return proto.list("","*").addCallback(select_mailbox, proto)

def connected(proto):
    d = proto.login(GATEWAY_EMAIL, PASSWORD)
    d.addCallback(list_mailboxes, proto)
    d.addErrback(login_failed)
    return d

def login_failed(failure):
    return failure

def done(_):
    reactor.callLater(0, reactor.stop)

def main():
    imap_client = protocol.ClientCreator(reactor, imap4.IMAP4Client)
    d = imap_client.connectSSL(SERVER, PORT, ssl.ClientContextFactory())
    d.addCallbacks(connected, login_failed)
    d.addBoth(done)

class Command(BaseCommand):
    help = """Forward emails set to @streams.zulip.com to Zulip.

Run this command out of a cron job.
"""

    def handle(self, **options):
        reactor.callLater(0, main)
        reactor.run()
