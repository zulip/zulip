# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase

from zerver.lib.test_helpers import (
    AuthedTestCase,
    most_recent_message,
    most_recent_usermessage,
)

from zerver.models import (
    get_display_recipient, get_stream, get_user_profile_by_email,
    Recipient,
)

from zerver.lib.actions import (
    encode_email_address,
)
from zerver.lib.email_mirror import (
    process_message, process_stream_message, ZulipEmailForwardError,
    create_missed_message_address,
)

from zerver.lib.notifications import (
    handle_missedmessage_emails,
)

from email.mime.text import MIMEText

import datetime
import time
import re
import ujson


class TestStreamEmailMessagesSuccess(AuthedTestCase):
    def test_receive_stream_email_messages_success(self):

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = "hamlet@zulip.com"
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.subject, incoming_valid_message['Subject'])

class TestStreamEmailMessagesEmptyBody(AuthedTestCase):
    def test_receive_stream_email_messages_empty_body(self):

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
        incoming_valid_message = MIMEText('')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = "hamlet@zulip.com"
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = "othello@zulip.com"

        exception_message = ""
        debug_info = {}

        # process_message eats the exception & logs an error which can't be parsed here
        # so calling process_stream_message directly
        try:
            process_stream_message(incoming_valid_message['To'],
                incoming_valid_message['Subject'],
                incoming_valid_message,
                debug_info)
        except ZulipEmailForwardError as e:
            # empty body throws exception
            exception_message = e.message
        self.assertEqual(exception_message, "Unable to find plaintext or HTML message body")

class TestMissedPersonalMessageEmailMessages(AuthedTestCase):
    def test_receive_missed_personal_message_email_messages(self):

        # build dummy messages for missed messages email reply
        # have Hamlet send Othello a PM. Othello will reply via email
        # Hamlet will receive the message.
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "content": "test_receive_missed_message_email_messages",
                                                         "client": "test suite",
                                                         "to": "othello@zulip.com"})
        self.assert_json_success(result)

        user_profile = get_user_profile_by_email("othello@zulip.com")
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedMessageEmailMessages Body')

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

class TestMissedHuddleMessageEmailMessages(AuthedTestCase):
    def test_receive_missed_huddle_message_email_messages(self):

        # build dummy messages for missed messages email reply
        # have Othello send Iago and Cordelia a PM. Cordelia will reply via email
        # Iago and Othello will receive the message.
        self.login("othello@zulip.com")
        result = self.client.post("/json/send_message", {"type": "private",
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

        incoming_valid_message = MIMEText('TestMissedHuddleMessageEmailMessages Body')

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
