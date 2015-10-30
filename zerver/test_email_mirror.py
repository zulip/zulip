# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase

from zerver.lib.test_helpers import (
    AuthedTestCase,
    most_recent_message,
)

from zerver.models import (
    get_display_recipient, get_stream, get_user_profile_by_email,
)

from zerver.lib.actions import (
    encode_email_address, do_update_message_flags,
)
from zerver.lib.email_mirror import (
    process_message, process_stream_message, ZulipEmailForwardError,
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
        headers = {}
        headers['Reply-To'] = 'othello@zulip.com'

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
        except ZulipEmailForwardError, e:
            # empty body throws exception
            exception_message = e.message
        self.assertEqual(exception_message, "Unable to find plaintext or HTML message body")
