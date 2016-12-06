# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase

from zerver.lib.test_helpers import (
    most_recent_message,
    most_recent_usermessage,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    get_display_recipient, get_stream, get_user_profile_by_email,
    Recipient, get_realm_by_string_id,
)

from zerver.lib.actions import (
    encode_email_address,
)
from zerver.lib.email_mirror import (
    process_message, process_stream_message, ZulipEmailForwardError,
    create_missed_message_address,
    get_missed_message_token_from_address,
)

from zerver.lib.digest import handle_digest_email

from zerver.lib.notifications import (
    handle_missedmessage_emails,
)

from email.mime.text import MIMEText

import datetime
import time
import re
import ujson
import mock
import os
import sys
from os.path import dirname, abspath
from six.moves import cStringIO as StringIO
from django.conf import settings

from zerver.lib.str_utils import force_str
from typing import Any, Callable, Mapping, Union, Text

class TestEmailMirrorLibrary(ZulipTestCase):
    def test_get_missed_message_token(self):
        # type: () -> None

        def get_token(address):
            # type: (Text) -> Text
            with self.settings(EMAIL_GATEWAY_PATTERN="%s@example.com"):
                return get_missed_message_token_from_address(address)

        address = 'mm' + ('x' * 32) + '@example.com'
        token = get_token(address)
        self.assertEqual(token, 'x' * 32)

        # This next section was a bug at one point--we'd treat ordinary
        # user addresses that happened to begin with "mm" as being
        # the special mm+32chars tokens.
        address = 'mmathers@example.com'
        with self.assertRaises(ZulipEmailForwardError):
            get_token(address)

        # Now test the case where we our address does not match the
        # EMAIL_GATEWAY_PATTERN.
        # This used to crash in an ugly way; we want to throw a proper
        # exception.
        address = 'alice@not-the-domain-we-were-expecting.com'
        with self.assertRaises(ZulipEmailForwardError):
            get_token(address)

class TestStreamEmailMessagesSuccess(ZulipTestCase):
    def test_receive_stream_email_messages_success(self):
        # type: () -> None

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body') # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = "hamlet@zulip.com"
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

class TestStreamEmailMessagesEmptyBody(ZulipTestCase):
    def test_receive_stream_email_messages_empty_body(self):
        # type: () -> None

        # build dummy messages for stream
        # test message with empty body is not sent
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        headers = {}
        headers['Reply-To'] = 'othello@zulip.com'

        # empty body
        incoming_valid_message = MIMEText('') # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = "hamlet@zulip.com"
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        exception_message = ""
        debug_info = {} # type: Dict[str, Any]

        # process_message eats the exception & logs an error which can't be parsed here
        # so calling process_stream_message directly
        try:
            process_stream_message(incoming_valid_message['To'],
                                   incoming_valid_message['Subject'],
                                   incoming_valid_message,
                                   debug_info)
        except ZulipEmailForwardError as e:
            # empty body throws exception
            exception_message = str(e)
        self.assertEqual(exception_message, "Unable to find plaintext or HTML message body")

class TestMissedPersonalMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_personal_message_email_messages(self):
        # type: () -> None

        # build dummy messages for missed messages email reply
        # have Hamlet send Othello a PM. Othello will reply via email
        # Hamlet will receive the message.
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_success(result)

        user_profile = get_user_profile_by_email("othello@zulip.com")
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedMessageEmailMessages Body') # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestMissedMessageEmailMessages Subject'
        incoming_valid_message['From'] = "othello@zulip.com"
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        process_message(incoming_valid_message)

        # self.login("hamlet@zulip.com")
        # confirm that Hamlet got the message
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedMessageEmailMessages Body")
        self.assertEqual(message.sender, get_user_profile_by_email("othello@zulip.com"))
        self.assertEqual(message.recipient.id, user_profile.id)
        self.assertEqual(message.recipient.type, Recipient.PERSONAL)

class TestMissedHuddleMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_huddle_message_email_messages(self):
        # type: () -> None

        # build dummy messages for missed messages email reply
        # have Othello send Iago and Cordelia a PM. Cordelia will reply via email
        # Iago and Othello will receive the message.
        self.login("othello@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": ujson.dumps(["cordelia@zulip.com",
                                                                        "iago@zulip.com"])})
        self.assert_json_success(result)

        user_profile = get_user_profile_by_email("cordelia@zulip.com")
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedHuddleMessageEmailMessages Body') # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestMissedHuddleMessageEmailMessages Subject'
        incoming_valid_message['From'] = "cordelia@zulip.com"
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = "cordelia@zulip.com"

        process_message(incoming_valid_message)

        # Confirm Iago received the message.
        user_profile = get_user_profile_by_email("iago@zulip.com")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages Body")
        self.assertEqual(message.sender, get_user_profile_by_email("cordelia@zulip.com"))
        self.assertEqual(message.recipient.type, Recipient.HUDDLE)

        # Confirm Othello received the message.
        user_profile = get_user_profile_by_email("othello@zulip.com")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages Body")
        self.assertEqual(message.sender, get_user_profile_by_email("cordelia@zulip.com"))
        self.assertEqual(message.recipient.type, Recipient.HUDDLE)

class TestMissedMessageAddressWithEmptyGateway(ZulipTestCase):
    def test_address_with_empty_gateway(self):
        # type: () -> None
        self.login("othello@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": ujson.dumps(["cordelia@zulip.com",
                                                                        "iago@zulip.com"])})
        self.assert_json_success(result)

        user_profile = get_user_profile_by_email("cordelia@zulip.com")
        usermessage = most_recent_usermessage(user_profile)
        with self.settings(EMAIL_GATEWAY_PATTERN=''):
            mm_address = create_missed_message_address(user_profile, usermessage.message)
            self.assertEqual(mm_address, settings.NOREPLY_EMAIL_ADDRESS)


class TestDigestEmailMessages(ZulipTestCase):
    @mock.patch('zerver.lib.digest.enough_traffic')
    @mock.patch('zerver.lib.digest.send_future_email')
    def test_receive_digest_email_messages(self, mock_send_future_email, mock_enough_traffic):
        # type: (mock.MagicMock, mock.MagicMock) -> None

        # build dummy messages for missed messages email reply
        # have Hamlet send Othello a PM. Othello will reply via email
        # Hamlet will receive the message.
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_success(result)

        user_profile = get_user_profile_by_email("othello@zulip.com")
        cutoff = time.mktime(datetime.datetime(year=2016, month=1, day=1).timetuple()) # type: ignore # https://github.com/python/typeshed/pull/597

        handle_digest_email(user_profile.id, cutoff)
        self.assertEqual(mock_send_future_email.call_count, 1)
        self.assertEqual(mock_send_future_email.call_args[0][0][0]['email'],
                         u'othello@zulip.com')

class TestReplyExtraction(ZulipTestCase):
    def test_reply_is_extracted_from_plain(self):
        # type: () -> None

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        text = """Reply

        -----Original Message-----

        Quote"""

        incoming_valid_message = MIMEText(text) # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = "hamlet@zulip.com"
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Reply")

    def test_reply_is_extracted_from_html(self):
        # type: () -> None

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        html = """
        <html>
            <body>
                <p>Reply</p>
                <blockquote>

                    <div>
                        On 11-Apr-2011, at 6:54 PM, Bob &lt;bob@example.com&gt; wrote:
                    </div>

                    <div>
                        Quote
                    </div>

                </blockquote>
            </body>
        </html>
        """

        incoming_valid_message = MIMEText(html, 'html') # type: Any # https://github.com/python/typeshed/issues/275

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = "hamlet@zulip.com"
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, 'Reply')

MAILS_DIR = os.path.join(dirname(dirname(abspath(__file__))), "fixtures", "email")

class TestCommandMTA(TestCase):

    @mock.patch('zerver.lib.queue.queue_json_publish')
    def test_success(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None

        sender = "hamlet@zulip.com"
        stream = get_stream("Denmark", get_realm_by_string_id("zulip"))
        stream_to_address = encode_email_address(stream)

        template_path = os.path.join(MAILS_DIR, "simple.txt")
        with open(template_path) as template_file:
            mail_template = template_file.read()
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)

        def check_queue_json_publish(queue_name, event, processor):
            # type: (str, Union[Mapping[str, Any], str], Callable[[Any], None]) -> None
            self.assertEqual(queue_name, "email_mirror")
            self.assertEqual(event, {"rcpt_to": stream_to_address, "message": mail})
        mock_queue_json_publish.side_effect = check_queue_json_publish

        original_stdin = sys.stdin
        try:
            sys.stdin = StringIO(mail)

            from zerver.management.commands import email_mirror
            command = email_mirror.Command()
            command.handle(recipient=force_str(stream_to_address))
        finally:
            sys.stdin = original_stdin
