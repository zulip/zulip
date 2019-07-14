# -*- coding: utf-8 -*-

import subprocess

from django.http import HttpResponse

from zerver.lib.test_helpers import (
    most_recent_message,
    most_recent_usermessage,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    get_display_recipient,
    get_realm,
    get_stream,
    get_system_bot,
    Recipient,
)

from zerver.lib.actions import ensure_stream

from zerver.lib.email_mirror import (
    process_message, process_missed_message,
    create_missed_message_address,
    get_missed_message_token_from_address,
    strip_from_subject,
    is_forwarded,
    is_missed_message_address,
    filter_footer,
    log_and_report,
    redact_email_address,
    ZulipEmailForwardError,
)

from zerver.lib.email_mirror_helpers import (
    decode_email_address,
    encode_email_address,
    get_email_gateway_message_string_from_address,
)

from zerver.lib.email_notifications import convert_html_to_markdown
from zerver.lib.send_email import FromAddress

from email import message_from_string
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

import ujson
import mock
import os
from django.conf import settings

from typing import Any, Callable, Dict, Mapping, Union, Optional

class TestEncodeDecode(ZulipTestCase):
    def _assert_options(self, options: Dict[str, bool], show_sender: bool=False,
                        include_footer: bool=False, include_quotes: bool=False) -> None:
        self.assertEqual(show_sender, ('show_sender' in options) and options['show_sender'])
        self.assertEqual(include_footer, ('include_footer' in options) and options['include_footer'])
        self.assertEqual(include_quotes, ('include_quotes' in options) and options['include_quotes'])

    def test_encode_decode(self) -> None:
        realm = get_realm('zulip')
        stream_name = 'dev. help'
        stream = ensure_stream(realm, stream_name)
        email_address = encode_email_address(stream)
        self.assertTrue(email_address.startswith('dev-help'))
        self.assertTrue(email_address.endswith('@testserver'))
        token, options = decode_email_address(email_address)
        self._assert_options(options)
        self.assertEqual(token, stream.email_token)

        parts = email_address.split('@')
        # Use a mix of + and . as separators, to test that it works:
        parts[0] += "+include-footer.show-sender+include-quotes"
        email_address_all_options = '@'.join(parts)
        token, options = decode_email_address(email_address_all_options)
        self._assert_options(options, show_sender=True, include_footer=True, include_quotes=True)
        self.assertEqual(token, stream.email_token)

        email_address = email_address.replace('@testserver', '@zulip.org')
        email_address_all_options = email_address_all_options.replace('@testserver', '@zulip.org')
        with self.assertRaises(ZulipEmailForwardError):
            decode_email_address(email_address)

        with self.assertRaises(ZulipEmailForwardError):
            decode_email_address(email_address_all_options)

        with self.settings(EMAIL_GATEWAY_EXTRA_PATTERN_HACK='@zulip.org'):
            token, options = decode_email_address(email_address)
            self._assert_options(options)
            self.assertEqual(token, stream.email_token)

            token, options = decode_email_address(email_address_all_options)
            self._assert_options(options, show_sender=True, include_footer=True, include_quotes=True)
            self.assertEqual(token, stream.email_token)

        with self.assertRaises(ZulipEmailForwardError):
            decode_email_address('bogus')

    # Test stream name encoding changes introduced due to
    # https://github.com/zulip/zulip/issues/9840
    def test_encode_decode_nonlatin_alphabet_stream_name(self) -> None:
        realm = get_realm('zulip')
        stream_name = 'Тестовы some ascii letters'
        stream = ensure_stream(realm, stream_name)
        email_address = encode_email_address(stream)

        msg_string = get_email_gateway_message_string_from_address(email_address)
        parts = msg_string.split('+')
        # Stream name should be completely stripped to '', so msg_string
        # should only have the email_token in it.
        self.assertEqual(len(parts), 1)

        # Correctly decode the resulting address that doesn't have the stream name:
        token, show_sender = decode_email_address(email_address)
        self.assertFalse(show_sender)
        self.assertEqual(token, stream.email_token)

        asciiable_stream_name = "ąężć"
        stream = ensure_stream(realm, asciiable_stream_name)
        email_address = encode_email_address(stream)
        self.assertTrue(email_address.startswith("aezc."))

    def test_decode_ignores_stream_name(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        stream_to_address = stream_to_address.replace("denmark", "Some_name")

        # get the email_token:
        token = decode_email_address(stream_to_address)[0]
        self.assertEqual(token, stream.email_token)

class TestGetMissedMessageToken(ZulipTestCase):
    def test_get_missed_message_token(self) -> None:
        with self.settings(EMAIL_GATEWAY_PATTERN="%s@example.com"):
            address = 'mm' + ('x' * 32) + '@example.com'
            self.assertTrue(is_missed_message_address(address))
            token = get_missed_message_token_from_address(address)
            self.assertEqual(token, 'x' * 32)

            # This next section was a bug at one point--we'd treat ordinary
            # user addresses that happened to begin with "mm" as being
            # the special mm+32chars tokens.
            address = 'mmathers@example.com'
            self.assertFalse(is_missed_message_address(address))
            with self.assertRaises(ZulipEmailForwardError):
                get_missed_message_token_from_address(address)

            # Now test the case where we our address does not match the
            # EMAIL_GATEWAY_PATTERN.
            # This used to crash in an ugly way; we want to throw a proper
            # exception.
            address = 'alice@not-the-domain-we-were-expecting.com'
            self.assertFalse(is_missed_message_address(address))
            with self.assertRaises(ZulipEmailForwardError):
                get_missed_message_token_from_address(address)

class TestFilterFooter(ZulipTestCase):
    def test_filter_footer(self) -> None:
        text = """Test message
        --
        Footer"""
        result = filter_footer(text)
        self.assertEqual(result, "Test message")

    def test_filter_footer_many_parts(self) -> None:
        text = """Test message
        --
        Part1
        --
        Part2"""
        result = filter_footer(text)
        # Multiple possible footers, don't strip
        self.assertEqual(result, text)

class TestStreamEmailMessagesSuccess(ZulipTestCase):
    def test_receive_stream_email_messages_success(self) -> None:

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

    def test_receive_stream_email_messages_blank_subject_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')

        incoming_valid_message['Subject'] = ''
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), "(no topic)")

    def test_receive_private_stream_email_messages_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.make_stream("private_stream", invite_only=True)
        self.subscribe(user_profile, "private_stream")
        stream = get_stream("private_stream", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

    def test_receive_stream_email_multiple_recipient_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        # stream address is angle-addr within multiple addresses
        stream_to_addresses = ["A.N. Other <another@example.org>",
                               "Denmark <{}>".format(encode_email_address(stream))]

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = ", ".join(stream_to_addresses)
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages Body")
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

    def test_receive_stream_email_show_sender_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        parts = stream_to_address.split('@')
        parts[0] += "+show-sender"
        stream_to_address = '@'.join(parts)

        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')
        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "From: %s\n%s" % (self.example_email('hamlet'),
                                                            "TestStreamEmailMessages Body"))
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

    def test_receive_stream_email_include_footer_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        parts = stream_to_address.split('@')
        parts[0] += "+include-footer"
        stream_to_address = '@'.join(parts)

        text = """Test message
        --
        Footer"""

        incoming_valid_message = MIMEText(text)
        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, text)
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

    def test_receive_stream_email_include_quotes_success(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        parts = stream_to_address.split('@')
        parts[0] += "+include-quotes"
        stream_to_address = '@'.join(parts)

        text = """Reply

        -----Original Message-----

        Quote"""

        incoming_valid_message = MIMEText(text)
        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, text)
        self.assertEqual(get_display_recipient(message.recipient), stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message['Subject'])

class TestEmailMirrorMessagesWithAttachments(ZulipTestCase):
    def test_message_with_valid_attachment(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEMultipart()
        text_msg = MIMEText("Test body")
        incoming_valid_message.attach(text_msg)
        with open(os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), 'rb') as f:
            image_bytes = f.read()

        attachment_msg = MIMEImage(image_bytes)
        attachment_msg.add_header('Content-Disposition', 'attachment', filename="image.png")
        incoming_valid_message.attach(attachment_msg)

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        with mock.patch('zerver.lib.email_mirror.upload_message_file',
                        return_value='https://test_url') as upload_message_file:
            process_message(incoming_valid_message)
            upload_message_file.assert_called_with('image.png', len(image_bytes),
                                                   'image/png', image_bytes,
                                                   get_system_bot(settings.EMAIL_GATEWAY_BOT),
                                                   target_realm=user_profile.realm)

        message = most_recent_message(user_profile)
        self.assertEqual(message.content, "Test body[image.png](https://test_url)")

    def test_message_with_invalid_attachment(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = MIMEMultipart()
        text_msg = MIMEText("Test body")
        incoming_valid_message.attach(text_msg)
        # Create an invalid attachment:
        attachment_msg = MIMEMultipart()
        attachment_msg.add_header('Content-Disposition', 'attachment', filename="some_attachment")
        incoming_valid_message.attach(attachment_msg)

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        with mock.patch('zerver.lib.email_mirror.logger.warning') as mock_warn:
            process_message(incoming_valid_message)
            mock_warn.assert_called_with("Payload is not bytes (invalid attachment %s in message from %s)." %
                                         ('some_attachment', self.example_email('hamlet')))

class TestStreamEmailMessagesEmptyBody(ZulipTestCase):
    def test_receive_stream_email_messages_empty_body(self) -> None:
        # build dummy messages for stream
        # test message with empty body is not sent
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        # empty body
        incoming_valid_message = MIMEText('')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        with mock.patch('zerver.lib.email_mirror.logging.warning') as mock_warn:
            process_message(incoming_valid_message)
            mock_warn.assert_called_with("Email has no nonempty body sections; ignoring.")

    def test_receive_stream_email_messages_no_textual_body(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)
        # No textual body
        incoming_valid_message = MIMEMultipart()
        with open(os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), 'rb') as f:
            incoming_valid_message.attach(MIMEImage(f.read()))

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        with mock.patch('zerver.lib.email_mirror.logging.warning') as mock_warn:
            process_message(incoming_valid_message)
            mock_warn.assert_called_with("Unable to find plaintext or HTML message body")

    def test_receive_stream_email_messages_empty_body_after_stripping(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        headers = {}
        headers['Reply-To'] = self.example_email('othello')

        # empty body
        incoming_valid_message = MIMEText('-- \nFooter')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "(No email body)")

class TestMissedMessageEmailMessageTokenMissingData(ZulipTestCase):
    # Test for the case "if not all(val is not None for val in result):"
    # on result returned by redis_client.hmget in send_to_missed_message_address:
    def test_receive_missed_message_email_token_missing_data(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_token_missing_data",
                                                     "client": "test suite",
                                                     "to": self.example_email('othello')})
        self.assert_json_success(result)

        user_profile = self.example_user('othello')
        usermessage = most_recent_usermessage(user_profile)

        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedMessageEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestMissedMessageEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('othello')
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        # We need to force redis_client.hmget to return some None values:
        with mock.patch('zerver.lib.email_mirror.redis_client.hmget',
                        return_value=[None, None, None]):
            exception_message = ''
            try:
                process_missed_message(mm_address, incoming_valid_message, False)
            except ZulipEmailForwardError as e:
                exception_message = str(e)

            self.assertEqual(exception_message, 'Missing missed message address data')

class TestMissedPersonalMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_personal_message_email_messages(self) -> None:

        # build dummy messages for missed messages email reply
        # have Hamlet send Othello a PM. Othello will reply via email
        # Hamlet will receive the message.
        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": self.example_email('othello')})
        self.assert_json_success(result)

        user_profile = self.example_user('othello')
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedMessageEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestMissedMessageEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('othello')
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # self.login(self.example_email("hamlet"))
        # confirm that Hamlet got the message
        user_profile = self.example_user('hamlet')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('othello'))
        self.assertEqual(message.recipient.id, user_profile.id)
        self.assertEqual(message.recipient.type, Recipient.PERSONAL)

class TestMissedHuddleMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_huddle_message_email_messages(self) -> None:

        # build dummy messages for missed messages email reply
        # have Othello send Iago and Cordelia a PM. Cordelia will reply via email
        # Iago and Othello will receive the message.
        email = self.example_email('othello')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": ujson.dumps([self.example_email('cordelia'),
                                                                        self.example_email('iago')])})
        self.assert_json_success(result)

        user_profile = self.example_user('cordelia')
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedHuddleMessageEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestMissedHuddleMessageEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('cordelia')
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = self.example_email('cordelia')

        process_message(incoming_valid_message)

        # Confirm Iago received the message.
        user_profile = self.example_user('iago')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('cordelia'))
        self.assertEqual(message.recipient.type, Recipient.HUDDLE)

        # Confirm Othello received the message.
        user_profile = self.example_user('othello')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('cordelia'))
        self.assertEqual(message.recipient.type, Recipient.HUDDLE)

class TestMissedStreamMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_stream_message_email_messages(self) -> None:
        # build dummy messages for missed messages email reply
        # have Hamlet send a message to stream Denmark, that Othello
        # will receive a missed message email about.
        # Othello will reply via email.
        # Hamlet will see the message in the stream.
        self.subscribe(self.example_user("hamlet"), "Denmark")
        self.subscribe(self.example_user("othello"), "Denmark")
        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "topic": "test topic",
                                                     "content": "test_receive_missed_stream_message_email_messages",
                                                     "client": "test suite",
                                                     "to": "Denmark"})
        self.assert_json_success(result)

        user_profile = self.example_user('othello')
        usermessage = most_recent_usermessage(user_profile)

        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = MIMEText('TestMissedMessageEmailMessages Body')

        incoming_valid_message['Subject'] = 'TestMissedMessageEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('othello')
        incoming_valid_message['To'] = mm_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # confirm that Hamlet got the message
        user_profile = self.example_user('hamlet')
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedMessageEmailMessages Body")
        self.assertEqual(message.sender, self.example_user('othello'))
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.recipient.id, usermessage.message.recipient.id)

class TestEmptyGatewaySetting(ZulipTestCase):
    def test_missed_message(self) -> None:
        email = self.example_email('othello')
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "test_receive_missed_message_email_messages",
                                                     "client": "test suite",
                                                     "to": ujson.dumps([self.example_email('cordelia'),
                                                                        self.example_email('iago')])})
        self.assert_json_success(result)

        user_profile = self.example_user('cordelia')
        usermessage = most_recent_usermessage(user_profile)
        with self.settings(EMAIL_GATEWAY_PATTERN=''):
            mm_address = create_missed_message_address(user_profile, usermessage.message)
            self.assertEqual(mm_address, FromAddress.NOREPLY)

    def test_encode_email_addr(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))

        with self.settings(EMAIL_GATEWAY_PATTERN=''):
            test_address = encode_email_address(stream)
            self.assertEqual(test_address, '')

class TestReplyExtraction(ZulipTestCase):
    def test_is_forwarded(self) -> None:
        self.assertTrue(is_forwarded("FWD: hey"))
        self.assertTrue(is_forwarded("fwd: hi"))
        self.assertTrue(is_forwarded("[fwd] subject"))

        self.assertTrue(is_forwarded("FWD: RE:"))
        self.assertTrue(is_forwarded("Fwd: RE: fwd: re: subject"))

        self.assertFalse(is_forwarded("subject"))
        self.assertFalse(is_forwarded("RE: FWD: hi"))

    def test_reply_is_extracted_from_plain(self) -> None:

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        email = self.example_email('hamlet')
        self.login(email)
        user_profile = self.example_user('hamlet')
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        text = """Reply

        -----Original Message-----

        Quote"""

        incoming_valid_message = MIMEText(text)

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Reply")

        # Don't extract if Subject indicates the email has been forwarded into the mirror:
        del incoming_valid_message['Subject']
        incoming_valid_message['Subject'] = 'FWD: TestStreamEmailMessages Subject'
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual(message.content, text)

    def test_reply_is_extracted_from_html(self) -> None:

        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        email = self.example_email('hamlet')
        self.login(email)
        user_profile = self.example_user('hamlet')
        self.subscribe(user_profile, "Denmark")
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

        incoming_valid_message = MIMEText(html, 'html')

        incoming_valid_message['Subject'] = 'TestStreamEmailMessages Subject'
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, 'Reply')

        # Don't extract if Subject indicates the email has been forwarded into the mirror:
        del incoming_valid_message['Subject']
        incoming_valid_message['Subject'] = 'FWD: TestStreamEmailMessages Subject'
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual(message.content, convert_html_to_markdown(html))

class TestScriptMTA(ZulipTestCase):

    def test_success(self) -> None:
        script = os.path.join(os.path.dirname(__file__),
                              '../../scripts/lib/email-mirror-postfix')

        sender = self.example_email('hamlet')
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)

        mail_template = self.fixture_data('simple.txt', type='email')
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)
        read_pipe, write_pipe = os.pipe()
        os.write(write_pipe, mail.encode())
        os.close(write_pipe)
        subprocess.check_call(
            [script, '-r', stream_to_address, '-s', settings.SHARED_SECRET, '-t'],
            stdin=read_pipe)

    def test_error_no_recipient(self) -> None:
        script = os.path.join(os.path.dirname(__file__),
                              '../../scripts/lib/email-mirror-postfix')

        sender = self.example_email('hamlet')
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        mail_template = self.fixture_data('simple.txt', type='email')
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)
        read_pipe, write_pipe = os.pipe()
        os.write(write_pipe, mail.encode())
        os.close(write_pipe)
        success_call = True
        try:
            subprocess.check_output([script, '-s', settings.SHARED_SECRET, '-t'],
                                    stdin=read_pipe)
        except subprocess.CalledProcessError as e:
            self.assertEqual(
                e.output,
                b'5.1.1 Bad destination mailbox address: No missed message email address.\n'
            )
            self.assertEqual(e.returncode, 67)
            success_call = False
        self.assertFalse(success_call)


class TestEmailMirrorTornadoView(ZulipTestCase):

    def send_private_message(self) -> str:
        email = self.example_email('othello')
        self.login(email)
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_receive_missed_message_email_messages",
                "client": "test suite",
                "to": ujson.dumps([self.example_email('cordelia'), self.example_email('iago')])
            })
        self.assert_json_success(result)

        user_profile = self.example_user('cordelia')
        user_message = most_recent_usermessage(user_profile)
        return create_missed_message_address(user_profile, user_message.message)

    @mock.patch('zerver.lib.email_mirror.queue_json_publish')
    def send_offline_message(self, to_address: str, sender: str,
                             mock_queue_json_publish: mock.Mock) -> HttpResponse:
        mail_template = self.fixture_data('simple.txt', type='email')
        mail = mail_template.format(stream_to_address=to_address, sender=sender)

        def check_queue_json_publish(queue_name: str,
                                     event: Union[Mapping[str, Any], str],
                                     processor: Optional[Callable[[Any], None]]=None) -> None:
            self.assertEqual(queue_name, "email_mirror")
            self.assertEqual(event, {"rcpt_to": to_address, "message": mail})

        mock_queue_json_publish.side_effect = check_queue_json_publish
        request_data = {
            "recipient": to_address,
            "msg_text": mail
        }
        post_data = dict(
            data=ujson.dumps(request_data),
            secret=settings.SHARED_SECRET
        )
        return self.client_post('/email_mirror_message', post_data)

    def test_success_stream(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        result = self.send_offline_message(stream_to_address, self.example_email('hamlet'))
        self.assert_json_success(result)

    def test_error_to_stream_with_wrong_address(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        # get the email_token:
        token = decode_email_address(stream_to_address)[0]
        stream_to_address = stream_to_address.replace(token, "Wrong_token")

        result = self.send_offline_message(stream_to_address, self.example_email('hamlet'))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: "
            "Please use the address specified in your Streams page.")

    def test_success_to_stream_with_good_token_wrong_stream_name(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        stream_to_address = stream_to_address.replace("denmark", "Wrong_name")

        result = self.send_offline_message(stream_to_address, self.example_email('hamlet'))
        self.assert_json_success(result)

    def test_success_to_private(self) -> None:
        mm_address = self.send_private_message()
        result = self.send_offline_message(mm_address, self.example_email('cordelia'))
        self.assert_json_success(result)

    def test_using_mm_address_twice(self) -> None:
        mm_address = self.send_private_message()
        self.send_offline_message(mm_address, self.example_email('cordelia'))
        result = self.send_offline_message(mm_address, self.example_email('cordelia'))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: Bad or expired missed message address.")

    def test_wrong_missed_email_private_message(self) -> None:
        self.send_private_message()
        mm_address = 'mm' + ('x' * 32) + '@testserver'
        result = self.send_offline_message(mm_address, self.example_email('cordelia'))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: Bad or expired missed message address.")


class TestStreamEmailMessagesSubjectStripping(ZulipTestCase):
    def test_process_message_strips_subject(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)
        incoming_valid_message = MIMEText('TestStreamEmailMessages Body')
        incoming_valid_message['Subject'] = "Re: Fwd: Re: Test"
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual("Test", message.topic_name())

        # If after stripping we get an empty subject, it should get set to (no topic)
        del incoming_valid_message['Subject']
        incoming_valid_message['Subject'] = "Re: Fwd: Re: "
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual("(no topic)", message.topic_name())

    def test_strip_from_subject(self) -> None:
        subject_list = ujson.loads(self.fixture_data('subjects.json', type='email'))
        for subject in subject_list:
            stripped = strip_from_subject(subject['original_subject'])
            self.assertEqual(stripped, subject['stripped_subject'])

# If the Content-Type header didn't specify a charset, the text content
# of the email used to not be properly found. Test that this is fixed:
class TestContentTypeUnspecifiedCharset(ZulipTestCase):
    def test_charset_not_specified(self) -> None:
        message_as_string = self.fixture_data('1.txt', type='email')
        message_as_string = message_as_string.replace("Content-Type: text/plain; charset=\"us-ascii\"",
                                                      "Content-Type: text/plain")
        incoming_message = message_from_string(message_as_string)

        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        del incoming_message['To']
        incoming_message['To'] = stream_to_address
        process_message(incoming_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Email fixture 1.txt body")

class TestEmailMirrorProcessMessageNoValidRecipient(ZulipTestCase):
    def test_process_message_no_valid_recipient(self) -> None:
        incoming_valid_message = MIMEText('Test Body')
        incoming_valid_message['Subject'] = "Test Subject"
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = "address@wrongdomain, address@notzulip"
        incoming_valid_message['Reply-to'] = self.example_email('othello')

        with mock.patch("zerver.lib.email_mirror.log_and_report") as mock_log_and_report:
            process_message(incoming_valid_message)
            mock_log_and_report.assert_called_with(incoming_valid_message,
                                                   "Missing recipient in mirror email", None)

class TestEmailMirrorLogAndReport(ZulipTestCase):
    def test_log_and_report(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "errors")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        address_parts = stream_to_address.split('@')
        scrubbed_address = 'X'*len(address_parts[0]) + '@' + address_parts[1]

        incoming_valid_message = MIMEText('Test Body')
        incoming_valid_message['Subject'] = "Test Subject"
        incoming_valid_message['From'] = self.example_email('hamlet')
        incoming_valid_message['To'] = stream_to_address

        log_and_report(incoming_valid_message, "test error message", stream_to_address)
        message = most_recent_message(user_profile)

        self.assertEqual("email mirror error", message.topic_name())

        msg_content = message.content.strip('~').strip()
        expected_content = "Sender: {}\nTo: {} <Address to stream id: {}>\ntest error message"
        expected_content = expected_content.format(self.example_email('hamlet'), scrubbed_address,
                                                   stream.id)
        self.assertEqual(msg_content, expected_content)

        log_and_report(incoming_valid_message, "test error message", None)
        message = most_recent_message(user_profile)
        self.assertEqual("email mirror error", message.topic_name())
        msg_content = message.content.strip('~').strip()
        expected_content = "Sender: {}\nTo: No recipient found\ntest error message"
        expected_content = expected_content.format(self.example_email('hamlet'))
        self.assertEqual(msg_content, expected_content)

    @mock.patch('zerver.lib.email_mirror.logger.error')
    def test_log_and_report_no_errorbot(self, mock_error: mock.MagicMock) -> None:
        with self.settings(ERROR_BOT=None):
            incoming_valid_message = MIMEText('Test Body')
            incoming_valid_message['Subject'] = "Test Subject"
            incoming_valid_message['From'] = self.example_email('hamlet')
            log_and_report(incoming_valid_message, "test error message", None)

            expected_content = "Sender: {}\nTo: No recipient found\ntest error message"
            expected_content = expected_content.format(self.example_email('hamlet'))
            mock_error.assert_called_with(expected_content)

    def test_redact_email_address(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "errors")
        stream = get_stream("Denmark", user_profile.realm)

        # Test for a stream address:
        stream_to_address = encode_email_address(stream)
        stream_address_parts = stream_to_address.split('@')
        scrubbed_stream_address = 'X'*len(stream_address_parts[0]) + '@' + stream_address_parts[1]

        error_message = "test message {}"
        error_message = error_message.format(stream_to_address)
        expected_message = "test message {} <Address to stream id: {}>"
        expected_message = expected_message.format(scrubbed_stream_address, stream.id)

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test for an invalid email address:
        invalid_address = "invalid@testserver"
        error_message = "test message {}"
        error_message = error_message.format(invalid_address)
        expected_message = "test message {} <Invalid address>"
        expected_message = expected_message.format('XXXXXXX@testserver')

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test for a missed message address:
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_redact_email_message",
                "client": "test suite",
                "to": ujson.dumps([self.example_email('cordelia'), self.example_email('iago')])
            })
        self.assert_json_success(result)

        cordelia_profile = self.example_user('cordelia')
        user_message = most_recent_usermessage(cordelia_profile)
        mm_address = create_missed_message_address(user_profile, user_message.message)

        error_message = "test message {}"
        error_message = error_message.format(mm_address)
        expected_message = "test message {} <Missed message address>"
        expected_message = expected_message.format('X'*34 + '@testserver')

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test if redacting correctly scrubs multiple occurrences of the address:
        error_message = "test message first occurrence: {} second occurrence: {}"
        error_message = error_message.format(stream_to_address, stream_to_address)
        expected_message = "test message first occurrence: {} <Address to stream id: {}>"
        expected_message += " second occurrence: {} <Address to stream id: {}>"
        expected_message = expected_message.format(scrubbed_stream_address, stream.id,
                                                   scrubbed_stream_address, stream.id)

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test with EMAIL_GATEWAY_EXTRA_PATTERN_HACK:
        with self.settings(EMAIL_GATEWAY_EXTRA_PATTERN_HACK='@zulip.org'):
            stream_to_address = stream_to_address.replace('@testserver', '@zulip.org')
            scrubbed_stream_address = scrubbed_stream_address.replace('@testserver', '@zulip.org')
            error_message = "test message {}"
            error_message = error_message.format(stream_to_address)
            expected_message = "test message {} <Address to stream id: {}>"
            expected_message = expected_message.format(scrubbed_stream_address, stream.id)

            redacted_message = redact_email_address(error_message)
            self.assertEqual(redacted_message, expected_message)
