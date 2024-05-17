import base64
import email.policy
import os
import subprocess
from email import message_from_string
from email.headerregistry import Address
from email.message import EmailMessage, MIMEPart
from typing import TYPE_CHECKING, Any, Callable, Dict, Mapping, Optional
from unittest import mock

import orjson
from django.conf import settings

from zerver.actions.realm_settings import do_deactivate_realm
from zerver.actions.streams import do_change_stream_post_policy
from zerver.actions.users import do_deactivate_user
from zerver.lib.email_mirror import (
    create_missed_message_address,
    filter_footer,
    get_missed_message_token_from_address,
    is_forwarded,
    is_missed_message_address,
    log_error,
    process_message,
    process_missed_message,
    redact_email_address,
    strip_from_subject,
)
from zerver.lib.email_mirror_helpers import (
    ZulipEmailForwardError,
    decode_email_address,
    encode_email_address,
    get_email_gateway_message_string_from_address,
)
from zerver.lib.email_notifications import convert_html_to_markdown
from zerver.lib.send_email import FromAddress
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish, most_recent_message, most_recent_usermessage
from zerver.models import Attachment, Recipient, Stream, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot
from zerver.worker.email_mirror import MirrorWorker

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

logger_name = "zerver.lib.email_mirror"


class TestEncodeDecode(ZulipTestCase):
    def _assert_options(
        self,
        options: Dict[str, bool],
        show_sender: bool = False,
        include_footer: bool = False,
        include_quotes: bool = False,
        prefer_text: bool = True,
    ) -> None:
        self.assertEqual(show_sender, ("show_sender" in options) and options["show_sender"])
        self.assertEqual(
            include_footer, ("include_footer" in options) and options["include_footer"]
        )
        self.assertEqual(
            include_quotes, ("include_quotes" in options) and options["include_quotes"]
        )
        self.assertEqual(prefer_text, options.get("prefer_text", True))

    def test_encode_decode(self) -> None:
        realm = get_realm("zulip")
        stream_name = "dev. help"
        stream = ensure_stream(realm, stream_name, acting_user=None)
        email_address = encode_email_address(stream)
        self.assertEqual(email_address, f"dev-help.{stream.email_token}@testserver")

        # The default form of the email address (with an option - "include-footer"):
        token, options = decode_email_address(
            f"dev-help.{stream.email_token}.include-footer@testserver",
        )
        self._assert_options(options, include_footer=True)
        self.assertEqual(token, stream.email_token)

        # Using + instead of . as the separator is also supported for backwards compatibility,
        # since that was the original form of addresses that we used:
        token, options = decode_email_address(
            f"dev-help+{stream.email_token}+include-footer@testserver",
        )
        self._assert_options(options, include_footer=True)
        self.assertEqual(token, stream.email_token)

        token, options = decode_email_address(email_address)
        self._assert_options(options)
        self.assertEqual(token, stream.email_token)

        # We also handle mixing + and . but it shouldn't be recommended to users.
        email_address_all_options = (
            "dev-help.{}+include-footer.show-sender+include-quotes@testserver"
        )
        email_address_all_options = email_address_all_options.format(stream.email_token)
        token, options = decode_email_address(email_address_all_options)
        self._assert_options(options, show_sender=True, include_footer=True, include_quotes=True)
        self.assertEqual(token, stream.email_token)

        email_address = email_address.replace("@testserver", "@zulip.org")
        email_address_all_options = email_address_all_options.replace("@testserver", "@zulip.org")
        with self.assertRaises(ZulipEmailForwardError):
            decode_email_address(email_address)

        with self.assertRaises(ZulipEmailForwardError):
            decode_email_address(email_address_all_options)

        with self.settings(EMAIL_GATEWAY_EXTRA_PATTERN_HACK="@zulip.org"):
            token, options = decode_email_address(email_address)
            self._assert_options(options)
            self.assertEqual(token, stream.email_token)

            token, options = decode_email_address(email_address_all_options)
            self._assert_options(
                options, show_sender=True, include_footer=True, include_quotes=True
            )
            self.assertEqual(token, stream.email_token)

        with self.assertRaises(ZulipEmailForwardError):
            decode_email_address("bogus")

    # Test stream name encoding changes introduced due to
    # https://github.com/zulip/zulip/issues/9840
    def test_encode_decode_nonlatin_alphabet_stream_name(self) -> None:
        realm = get_realm("zulip")
        stream_name = "Тестовы some ascii letters"
        stream = ensure_stream(realm, stream_name, acting_user=None)
        email_address = encode_email_address(stream)

        msg_string = get_email_gateway_message_string_from_address(email_address)
        parts = msg_string.split("+")
        # Stream name should be completely stripped to '', so msg_string
        # should only have the email_token in it.
        self.assert_length(parts, 1)

        # Correctly decode the resulting address that doesn't have the stream name:
        token, show_sender = decode_email_address(email_address)
        self.assertFalse(show_sender)
        self.assertEqual(token, stream.email_token)

        asciiable_stream_name = "ąężć"
        stream = ensure_stream(realm, asciiable_stream_name, acting_user=None)
        email_address = encode_email_address(stream)
        self.assertTrue(email_address.startswith("aezc."))

    def test_decode_ignores_stream_name(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        stream_to_address = stream_to_address.replace("denmark", "Some_name")

        # get the email_token:
        token = decode_email_address(stream_to_address)[0]
        self.assertEqual(token, stream.email_token)

    def test_encode_with_show_sender(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream, show_sender=True)

        token, options = decode_email_address(stream_to_address)
        self._assert_options(options, show_sender=True)
        self.assertEqual(token, stream.email_token)

    def test_decode_prefer_text_options(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        address_prefer_text = f"Denmark.{stream.email_token}.prefer-text@testserver"
        address_prefer_html = f"Denmark.{stream.email_token}.prefer-html@testserver"

        token, options = decode_email_address(address_prefer_text)
        self._assert_options(options, prefer_text=True)

        token, options = decode_email_address(address_prefer_html)
        self._assert_options(options, prefer_text=False)


class TestGetMissedMessageToken(ZulipTestCase):
    def test_get_missed_message_token(self) -> None:
        with self.settings(EMAIL_GATEWAY_PATTERN="%s@example.com"):
            address = "mm" + ("x" * 32) + "@example.com"
            self.assertTrue(is_missed_message_address(address))
            token = get_missed_message_token_from_address(address)
            self.assertEqual(token, "mm" + "x" * 32)

            # This next section was a bug at one point--we'd treat ordinary
            # user addresses that happened to begin with "mm" as being
            # the special mm+32chars tokens.
            address = "mmathers@example.com"
            self.assertFalse(is_missed_message_address(address))
            with self.assertRaises(ZulipEmailForwardError):
                get_missed_message_token_from_address(address)

            # Now test the case where we our address does not match the
            # EMAIL_GATEWAY_PATTERN.
            # This used to crash in an ugly way; we want to throw a proper
            # exception.
            address = "alice@not-the-domain-we-were-expecting.com"
            self.assertFalse(is_missed_message_address(address))
            with self.assertRaises(ZulipEmailForwardError):
                get_missed_message_token_from_address(address)


class TestFilterFooter(ZulipTestCase):
    def test_filter_footer(self) -> None:
        text = """Test message
        --Not a delimiter--
        More message
        --
        Footer"""
        expected_output = """Test message
        --Not a delimiter--
        More message"""
        result = filter_footer(text)
        self.assertEqual(result, expected_output)

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
    def create_incoming_valid_message(
        self, msgtext: str, stream: Stream, include_quotes: bool
    ) -> EmailMessage:
        address = Address(addr_spec=encode_email_address(stream))
        email_username = address.username + "+show-sender"
        if include_quotes:
            email_username += "+include-quotes"
        stream_to_address = Address(username=email_username, domain=address.domain).addr_spec

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content(msgtext)
        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")
        return incoming_valid_message

    def test_receive_stream_email_messages_success(self) -> None:
        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages body")
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    # Test receiving an email with the address on an UnstructuredHeader
    # (e.g. Envelope-To) instead of an AddressHeader (e.g. To).
    # https://github.com/zulip/zulip/issues/15864
    def test_receive_stream_email_messages_other_header_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        # Simulate a mailing list
        incoming_valid_message["To"] = "foo-mailinglist@example.com"
        incoming_valid_message["Envelope-To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages body")
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    def test_receive_stream_email_messages_blank_subject_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")

        incoming_valid_message["Subject"] = ""
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages body")
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), "(no topic)")

    def test_receive_stream_email_messages_subject_with_nonprintable_chars(
        self,
    ) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")

        incoming_valid_message["Subject"] = "Test \u0000 subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        message = most_recent_message(user_profile)

        self.assertEqual(message.topic_name(), "Test  subject")

        # Now check that a subject that will be stripped to the empty string
        # is handled correctly.
        incoming_valid_message.replace_header("Subject", "\u0000")
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.topic_name(), "(no topic)")

    def test_receive_private_stream_email_messages_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.make_stream("private_stream", invite_only=True)
        self.subscribe(user_profile, "private_stream")
        stream = get_stream("private_stream", user_profile.realm)

        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages body")
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    def test_receive_stream_email_multiple_recipient_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        # stream address is angle-addr within multiple addresses
        stream_to_addresses = [
            "A.N. Other <another@example.org>",
            f"Denmark <{encode_email_address(stream)}>",
        ]

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = ", ".join(stream_to_addresses)
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestStreamEmailMessages body")
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    def test_receive_stream_email_show_sender_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        msgtext = "TestStreamEmailMessages Body"
        incoming_valid_message = self.create_incoming_valid_message(
            msgtext, stream, include_quotes=False
        )
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(
            message.content,
            "From: {}\n{}".format(self.example_email("hamlet"), msgtext),
        )
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    def test_receive_stream_email_forwarded_success(self) -> None:
        msgtext = """
Hello! Here is a message I am forwarding to this list.
I hope you enjoy reading it!
-Glen

From: John Doe johndoe@wherever
To: A Zulip-subscribed mailing list somelist@elsewhere
Subject: Some subject

Here is the original email. It is full of text
and other things
-John
"""
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        def send_and_check_contents(
            msgtext: str, stream: Stream, include_quotes: bool, expected_body: str
        ) -> None:
            incoming_valid_message = self.create_incoming_valid_message(
                msgtext, stream, include_quotes
            )
            process_message(incoming_valid_message)
            message = most_recent_message(user_profile)
            expected = "From: {}\n{}".format(self.example_email("hamlet"), expected_body)
            self.assertEqual(message.content, expected.strip())
            self.assert_message_stream_name(message, stream.name)
            self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

        # include_quotes=True: expect the From:... to be preserved
        send_and_check_contents(msgtext, stream, include_quotes=True, expected_body=msgtext)

        # include_quotes=False: expect the From:... to be stripped
        send_and_check_contents(
            msgtext,
            stream,
            include_quotes=False,
            expected_body="Hello! Here is a message I am forwarding to this list.\nI hope you enjoy reading it!\n-Glen",
        )

    def test_receive_stream_email_show_sender_utf8_encoded_sender(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        address = Address(addr_spec=encode_email_address(stream))
        email_username = address.username + "+show-sender"
        stream_to_address = Address(username=email_username, domain=address.domain).addr_spec

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")
        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = (
            "Test =?utf-8?b?VXNlcsOzxIXEmQ==?= <=?utf-8?q?hamlet=5F=C4=99?=@zulip.com>"
        )
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(
            message.content,
            "From: {}\n{}".format(
                "Test Useróąę <hamlet_ę@zulip.com>", "TestStreamEmailMessages body"
            ),
        )
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    def test_receive_stream_email_include_footer_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        address = Address(addr_spec=encode_email_address(stream))
        email_username = address.username + "+include-footer"
        stream_to_address = Address(username=email_username, domain=address.domain).addr_spec

        text = """Test message
        --
        Footer"""

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content(text)
        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, text)
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])

    def test_receive_stream_email_include_quotes_success(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        address = Address(addr_spec=encode_email_address(stream))
        email_username = address.username + "+include-quotes"
        stream_to_address = Address(username=email_username, domain=address.domain).addr_spec

        text = """Reply

        -----Original Message-----

        Quote"""

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content(text)
        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, text)
        self.assert_message_stream_name(message, stream.name)
        self.assertEqual(message.topic_name(), incoming_valid_message["Subject"])


class TestEmailMirrorMessagesWithAttachments(ZulipTestCase):
    def test_message_with_valid_attachment(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            image_bytes = f.read()

        incoming_valid_message.add_attachment(
            image_bytes,
            maintype="image",
            subtype="png",
            filename="image.png",
        )

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with mock.patch(
            "zerver.lib.email_mirror.upload_message_attachment",
            return_value="https://test_url",
        ) as upload_message_attachment:
            process_message(incoming_valid_message)
            upload_message_attachment.assert_called_with(
                "image.png",
                len(image_bytes),
                "image/png",
                image_bytes,
                get_system_bot(settings.EMAIL_GATEWAY_BOT, stream.realm_id),
                target_realm=user_profile.realm,
            )

        message = most_recent_message(user_profile)
        self.assertEqual(message.content, "Test body\n\n[image.png](https://test_url)")

    def test_message_with_valid_attachment_model_attributes_set_correctly(self) -> None:
        """
        Verifies that the Attachment attributes are set correctly.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            image_bytes = f.read()

        incoming_valid_message.add_attachment(
            image_bytes,
            maintype="image",
            subtype="png",
            filename="image.png",
        )

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        message = most_recent_message(user_profile)
        attachment = Attachment.objects.last()
        assert attachment is not None
        self.assertEqual(list(attachment.messages.values_list("id", flat=True)), [message.id])
        self.assertEqual(
            message.sender, get_system_bot(settings.EMAIL_GATEWAY_BOT, stream.realm_id)
        )
        self.assertEqual(attachment.realm, stream.realm)
        self.assertEqual(attachment.is_realm_public, True)

    def test_message_with_attachment_long_body(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("a" * settings.MAX_MESSAGE_LENGTH)
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            image_bytes = f.read()

        incoming_valid_message.add_attachment(
            image_bytes,
            maintype="image",
            subtype="png",
            filename="image.png",
        )

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        message = most_recent_message(user_profile)
        attachment = Attachment.objects.last()
        assert attachment is not None
        self.assertEqual(list(attachment.messages.values_list("id", flat=True)), [message.id])
        self.assertEqual(
            message.sender, get_system_bot(settings.EMAIL_GATEWAY_BOT, stream.realm_id)
        )
        self.assertEqual(attachment.realm, stream.realm)
        self.assertEqual(attachment.is_realm_public, True)

        assert message.content.endswith(
            f"aaaaaa\n[message truncated]\n[image.png](/user_uploads/{attachment.path_id})"
        )

    def test_message_with_attachment_utf8_filename(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            image_bytes = f.read()

        utf8_filename = "image_ąęó.png"
        incoming_valid_message.add_attachment(
            image_bytes,
            maintype="image",
            subtype="png",
            filename=utf8_filename,
        )

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with mock.patch(
            "zerver.lib.email_mirror.upload_message_attachment",
            return_value="https://test_url",
        ) as upload_message_attachment:
            process_message(incoming_valid_message)
            upload_message_attachment.assert_called_with(
                utf8_filename,
                len(image_bytes),
                "image/png",
                image_bytes,
                get_system_bot(settings.EMAIL_GATEWAY_BOT, stream.realm_id),
                target_realm=user_profile.realm,
            )

        message = most_recent_message(user_profile)
        self.assertEqual(message.content, f"Test body\n\n[{utf8_filename}](https://test_url)")

    def test_message_with_valid_nested_attachment(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")

        nested_multipart = EmailMessage()
        nested_multipart.set_content("Nested text that should get skipped.")
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            image_bytes = f.read()

        nested_multipart.add_attachment(
            image_bytes,
            maintype="image",
            subtype="png",
            filename="image.png",
        )
        incoming_valid_message.add_attachment(nested_multipart)

        incoming_valid_message["Subject"] = "Subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with mock.patch(
            "zerver.lib.email_mirror.upload_message_attachment",
            return_value="https://test_url",
        ) as upload_message_attachment:
            process_message(incoming_valid_message)
            upload_message_attachment.assert_called_with(
                "image.png",
                len(image_bytes),
                "image/png",
                image_bytes,
                get_system_bot(settings.EMAIL_GATEWAY_BOT, stream.realm_id),
                target_realm=user_profile.realm,
            )

        message = most_recent_message(user_profile)
        self.assertEqual(message.content, "Test body\n\n[image.png](https://test_url)")

    def test_message_with_invalid_attachment(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        # Create an invalid attachment:
        attachment_msg = MIMEPart()
        attachment_msg.add_header("Content-Disposition", "attachment", filename="some_attachment")
        incoming_valid_message.add_attachment(attachment_msg)

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with self.assertLogs(logger_name, level="WARNING") as m:
            process_message(incoming_valid_message)
        self.assertEqual(
            m.output,
            [
                "WARNING:{}:Payload is not bytes (invalid attachment {} in message from {}).".format(
                    logger_name, "some_attachment", self.example_email("hamlet")
                )
            ],
        )

    def test_receive_plaintext_and_html_prefer_text_html_options(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_address = f"Denmark.{stream.email_token}@testserver"
        stream_address_prefer_html = f"Denmark.{stream.email_token}.prefer-html@testserver"

        text = "Test message"
        html = "<html><body><b>Test html message</b></body></html>"

        incoming_valid_message = EmailMessage()
        incoming_valid_message.add_alternative(text)
        incoming_valid_message.add_alternative(html, subtype="html")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Test message")

        del incoming_valid_message["To"]
        incoming_valid_message["To"] = stream_address_prefer_html

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "**Test html message**")

    def test_receive_only_plaintext_with_prefer_html_option(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_address_prefer_html = f"Denmark.{stream.email_token}.prefer-html@testserver"

        text = "Test message"
        # This should be correctly identified as empty html body:
        html = "<html><body></body></html>"

        incoming_valid_message = EmailMessage()
        incoming_valid_message.add_alternative(text)
        incoming_valid_message.add_alternative(html, subtype="html")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_address_prefer_html
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        # HTML body is empty, so the plaintext content should be picked, despite prefer-html option.
        self.assertEqual(message.content, "Test message")

    def test_message_with_valid_attachment_missed_message(self) -> None:
        user_profile = self.example_user("othello")
        usermessage = most_recent_usermessage(user_profile)
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            image_bytes = f.read()

        incoming_valid_message.add_attachment(
            image_bytes,
            maintype="image",
            subtype="png",
            filename="image.png",
        )

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("othello")
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)

        message = most_recent_message(user_profile)
        self.assertEqual(message.sender, user_profile)
        self.assertTrue(message.has_attachment)

        attachment = Attachment.objects.last()
        assert attachment is not None
        self.assertEqual(attachment.realm, user_profile.realm)
        self.assertEqual(attachment.owner, user_profile)
        self.assertEqual(attachment.is_realm_public, True)
        self.assertEqual(list(attachment.messages.values_list("id", flat=True)), [message.id])


class TestStreamEmailMessagesEmptyBody(ZulipTestCase):
    def test_receive_stream_email_messages_empty_body(self) -> None:
        # build dummy messages for stream
        # test message with empty body is not sent
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        # empty body
        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with self.assertLogs(logger_name, level="INFO") as m:
            process_message(incoming_valid_message)
        self.assertEqual(
            m.output,
            [f"INFO:{logger_name}:Email has no nonempty body sections; ignoring."],
        )

    def test_receive_stream_email_messages_no_textual_body(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)
        # No textual body
        incoming_valid_message = EmailMessage()
        with open(
            os.path.join(settings.DEPLOY_ROOT, "static/images/default-avatar.png"), "rb"
        ) as f:
            incoming_valid_message.add_attachment(
                f.read(),
                maintype="image",
                subtype="png",
            )

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with self.assertLogs(logger_name, level="INFO") as m:
            process_message(incoming_valid_message)
        self.assertEqual(
            m.output,
            [
                f"WARNING:{logger_name}:Content types: ['multipart/mixed', 'image/png']",
                f"INFO:{logger_name}:Unable to find plaintext or HTML message body",
            ],
        )

    def test_receive_stream_email_messages_empty_body_after_stripping(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        headers = {}
        headers["Reply-To"] = self.example_email("othello")

        # empty body
        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("-- \nFooter")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "(No email body)")


class TestMissedMessageEmailMessages(ZulipTestCase):
    def test_receive_missed_personal_message_email_messages(self) -> None:
        # Build dummy messages for message notification email reply.
        # Have Hamlet send Othello a direct message. Othello will
        # reply via email Hamlet will receive the message.
        self.login("hamlet")
        othello = self.example_user("othello")
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_receive_missed_message_email_messages",
                "to": orjson.dumps([othello.id]).decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("othello")
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("othello")
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with self.assert_database_query_count(16):
            process_message(incoming_valid_message)

        # confirm that Hamlet got the message
        user_profile = self.example_user("hamlet")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedMessageEmailMessages body")
        self.assertEqual(message.sender, self.example_user("othello"))
        self.assertEqual(message.recipient.type_id, user_profile.id)
        self.assertEqual(message.recipient.type, Recipient.PERSONAL)

    def test_receive_missed_huddle_message_email_messages(self) -> None:
        # Build dummy messages for message notification email reply.
        # Have Othello send Iago and Cordelia a group direct message.
        # Cordelia will reply via email Iago and Othello will receive
        # the message.
        self.login("othello")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_receive_missed_message_email_messages",
                "to": orjson.dumps([cordelia.id, iago.id]).decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("cordelia")
        usermessage = most_recent_usermessage(user_profile)

        # we don't want to send actual emails but we do need to create and store the
        # token for looking up who did reply.
        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedHuddleMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedHuddleMessageEmailMessages subject"
        incoming_valid_message["From"] = self.example_email("cordelia")
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = self.example_email("cordelia")

        with self.assert_database_query_count(21):
            process_message(incoming_valid_message)

        # Confirm Iago received the message.
        user_profile = self.example_user("iago")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages body")
        self.assertEqual(message.sender, self.example_user("cordelia"))
        self.assertEqual(message.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)

        # Confirm Othello received the message.
        user_profile = self.example_user("othello")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedHuddleMessageEmailMessages body")
        self.assertEqual(message.sender, self.example_user("cordelia"))
        self.assertEqual(message.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)

    def test_receive_missed_stream_message_email_messages(self) -> None:
        # build dummy messages for message notification email reply
        # have Hamlet send a message to stream Denmark, that Othello
        # will receive a message notification email about.
        # Othello will reply via email.
        # Hamlet will see the message in the stream.
        self.subscribe(self.example_user("hamlet"), "Denmark")
        self.subscribe(self.example_user("othello"), "Denmark")
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "topic": "test topic",
                "content": "test_receive_missed_stream_message_email_messages",
                "to": orjson.dumps("Denmark").decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("othello")
        usermessage = most_recent_usermessage(user_profile)

        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        with self.assert_database_query_count(17):
            process_message(incoming_valid_message)

        # confirm that Hamlet got the message
        user_profile = self.example_user("hamlet")
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "TestMissedMessageEmailMessages body")
        self.assertEqual(message.sender, self.example_user("othello"))
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.recipient.id, usermessage.message.recipient.id)

    def test_receive_email_response_for_auth_failures(self) -> None:
        user_profile = self.example_user("hamlet")
        self.subscribe(user_profile, "announce")
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "topic": "test topic",
                "content": "test_receive_email_response_for_auth_failures",
                "to": orjson.dumps("announce").decode(),
            },
        )
        self.assert_json_success(result)

        stream = get_stream("announce", user_profile.realm)
        do_change_stream_post_policy(
            stream, Stream.STREAM_POST_POLICY_ADMINS, acting_user=user_profile
        )

        usermessage = most_recent_usermessage(user_profile)

        mm_address = create_missed_message_address(user_profile, usermessage.message)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        process_message(incoming_valid_message)

        message = most_recent_message(user_profile)

        self.assertEqual(
            message.content,
            "Error sending message to channel announce via message notification email reply:\nOnly organization administrators can send to this channel.",
        )
        self.assertEqual(
            message.sender,
            get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id),
        )

    def test_missed_stream_message_email_response_tracks_topic_change(self) -> None:
        self.subscribe(self.example_user("hamlet"), "Denmark")
        self.subscribe(self.example_user("othello"), "Denmark")
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "topic": "test topic",
                "content": "test_receive_missed_stream_message_email_messages",
                "to": orjson.dumps("Denmark").decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("othello")
        usermessage = most_recent_usermessage(user_profile)

        mm_address = create_missed_message_address(user_profile, usermessage.message)

        # The mm address has been generated, now we change the topic of the message and see
        # if the response to the mm address will be correctly posted with the updated topic.
        usermessage.message.subject = "updated topic"
        usermessage.message.save(update_fields=["subject"])

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        process_message(incoming_valid_message)

        # confirm that Hamlet got the message
        user_profile = self.example_user("hamlet")
        message = most_recent_message(user_profile)

        self.assertEqual(message.subject, "updated topic")
        self.assertEqual(message.content, "TestMissedMessageEmailMessages body")
        self.assertEqual(message.sender, self.example_user("othello"))
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.recipient.id, usermessage.message.recipient.id)

    def test_missed_message_email_response_from_deactivated_user(self) -> None:
        self.subscribe(self.example_user("hamlet"), "Denmark")
        self.subscribe(self.example_user("othello"), "Denmark")
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "topic": "test topic",
                "content": "test_receive_missed_stream_message_email_messages",
                "to": orjson.dumps("Denmark").decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("othello")
        message = most_recent_message(user_profile)

        mm_address = create_missed_message_address(user_profile, message)

        do_deactivate_user(user_profile, acting_user=None)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        initial_last_message = self.get_last_message()
        process_message(incoming_valid_message)

        # Since othello is deactivated, his message shouldn't be posted:
        self.assertEqual(initial_last_message, self.get_last_message())

    def test_missed_message_email_response_from_deactivated_realm(self) -> None:
        self.subscribe(self.example_user("hamlet"), "Denmark")
        self.subscribe(self.example_user("othello"), "Denmark")
        self.login("hamlet")
        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "topic": "test topic",
                "content": "test_receive_missed_stream_message_email_messages",
                "to": orjson.dumps("Denmark").decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("othello")
        message = most_recent_message(user_profile)

        mm_address = create_missed_message_address(user_profile, message)

        do_deactivate_realm(user_profile.realm, acting_user=None)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        initial_last_message = self.get_last_message()
        process_message(incoming_valid_message)

        # Since othello's realm is deactivated, his message shouldn't be posted:
        self.assertEqual(initial_last_message, self.get_last_message())

    def test_missed_message_email_multiple_responses(self) -> None:
        self.subscribe(self.example_user("hamlet"), "Denmark")
        self.subscribe(self.example_user("othello"), "Denmark")
        self.login("hamlet")

        result = self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "topic": "test topic",
                "content": "test_receive_missed_stream_message_email_messages",
                "to": orjson.dumps("Denmark").decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("othello")
        message = most_recent_message(user_profile)

        mm_address = create_missed_message_address(user_profile, message)
        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestMissedMessageEmailMessages body")

        incoming_valid_message["Subject"] = "TestMissedMessageEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = mm_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        # there is no longer a usage limit.  Ensure we can send multiple times.
        for i in range(5):
            process_missed_message(mm_address, incoming_valid_message)


class TestEmptyGatewaySetting(ZulipTestCase):
    def test_missed_message(self) -> None:
        self.login("othello")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        payload = dict(
            type="private",
            content="test_receive_missed_message_email_messages",
            to=orjson.dumps([cordelia.id, iago.id]).decode(),
        )
        result = self.client_post("/json/messages", payload)
        self.assert_json_success(result)

        user_profile = self.example_user("cordelia")
        usermessage = most_recent_usermessage(user_profile)
        with self.settings(EMAIL_GATEWAY_PATTERN=""):
            mm_address = create_missed_message_address(user_profile, usermessage.message)
            self.assertEqual(mm_address, FromAddress.NOREPLY)

    def test_encode_email_addr(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))

        with self.settings(EMAIL_GATEWAY_PATTERN=""):
            test_address = encode_email_address(stream)
            self.assertEqual(test_address, "")


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
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)

        stream_to_address = encode_email_address(stream)
        text = """Reply

        -----Original Message-----

        Quote"""

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content(text)

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Reply")

        # Don't extract if Subject indicates the email has been forwarded into the mirror:
        del incoming_valid_message["Subject"]
        incoming_valid_message["Subject"] = "FWD: TestStreamEmailMessages subject"
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual(message.content, text)

    def test_reply_is_extracted_from_html(self) -> None:
        # build dummy messages for stream
        # test valid incoming stream message is processed properly
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
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

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content(html, subtype="html")

        incoming_valid_message["Subject"] = "TestStreamEmailMessages subject"
        incoming_valid_message["From"] = user_profile.delivery_email
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = user_profile.delivery_email

        process_message(incoming_valid_message)

        # Hamlet is subscribed to this stream so should see the email message from Othello.
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Reply")

        # Don't extract if Subject indicates the email has been forwarded into the mirror:
        del incoming_valid_message["Subject"]
        incoming_valid_message["Subject"] = "FWD: TestStreamEmailMessages subject"
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual(message.content, convert_html_to_markdown(html))


class TestScriptMTA(ZulipTestCase):
    def test_success(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "../../scripts/lib/email-mirror-postfix")

        sender = self.example_email("hamlet")
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)

        mail_template = self.fixture_data("simple.txt", type="email")
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)
        subprocess.run(
            [script, "-r", stream_to_address, "-s", settings.SHARED_SECRET, "-t"],
            input=mail,
            check=True,
            text=True,
        )

    def test_error_no_recipient(self) -> None:
        script = os.path.join(os.path.dirname(__file__), "../../scripts/lib/email-mirror-postfix")

        sender = self.example_email("hamlet")
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        mail_template = self.fixture_data("simple.txt", type="email")
        mail = mail_template.format(stream_to_address=stream_to_address, sender=sender)
        p = subprocess.run(
            [script, "-s", settings.SHARED_SECRET, "-t"],
            input=mail,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(
            p.stdout,
            "5.1.1 Bad destination mailbox address: No missed message email address.\n",
        )
        self.assertEqual(p.returncode, 67)


class TestEmailMirrorTornadoView(ZulipTestCase):
    def send_private_message(self) -> str:
        self.login("othello")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_receive_missed_message_email_messages",
                "to": orjson.dumps([cordelia.id, iago.id]).decode(),
            },
        )
        self.assert_json_success(result)

        user_profile = self.example_user("cordelia")
        user_message = most_recent_usermessage(user_profile)
        return create_missed_message_address(user_profile, user_message.message)

    def send_offline_message(self, to_address: str, sender: UserProfile) -> "TestHttpResponse":
        mail_template = self.fixture_data("simple.txt", type="email")
        mail = mail_template.format(stream_to_address=to_address, sender=sender.delivery_email)
        msg_base64 = base64.b64encode(mail.encode()).decode()

        def check_queue_json_publish(
            queue_name: str,
            event: Mapping[str, Any],
            processor: Optional[Callable[[Any], None]] = None,
        ) -> None:
            self.assertEqual(queue_name, "email_mirror")
            self.assertEqual(event, {"rcpt_to": to_address, "msg_base64": msg_base64})
            MirrorWorker().consume(event)

            self.assertEqual(
                self.get_last_message().content,
                "This is a plain-text message for testing Zulip.",
            )

        post_data = {
            "rcpt_to": to_address,
            "msg_base64": msg_base64,
            "secret": settings.SHARED_SECRET,
        }

        with mock_queue_publish("zerver.lib.email_mirror.queue_json_publish") as m:
            m.side_effect = check_queue_json_publish
            return self.client_post("/api/internal/email_mirror_message", post_data)

    def test_success_stream(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        result = self.send_offline_message(stream_to_address, self.example_user("hamlet"))
        self.assert_json_success(result)

    def test_error_to_stream_with_wrong_address(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        # get the email_token:
        token = decode_email_address(stream_to_address)[0]
        stream_to_address = stream_to_address.replace(token, "Wrong_token")

        result = self.send_offline_message(stream_to_address, self.example_user("hamlet"))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: "
            "Bad stream token from email recipient " + stream_to_address,
        )

    def test_success_to_stream_with_good_token_wrong_stream_name(self) -> None:
        stream = get_stream("Denmark", get_realm("zulip"))
        stream_to_address = encode_email_address(stream)
        stream_to_address = stream_to_address.replace("denmark", "Wrong_name")

        result = self.send_offline_message(stream_to_address, self.example_user("hamlet"))
        self.assert_json_success(result)

    def test_success_to_private(self) -> None:
        mm_address = self.send_private_message()
        result = self.send_offline_message(mm_address, self.example_user("cordelia"))
        self.assert_json_success(result)

    def test_using_mm_address_multiple_times(self) -> None:
        mm_address = self.send_private_message()
        # there is no longer a usage limit.  Ensure we can send multiple times.
        for i in range(5):
            result = self.send_offline_message(mm_address, self.example_user("cordelia"))
            self.assert_json_success(result)

    def test_wrong_missed_email_private_message(self) -> None:
        self.send_private_message()
        mm_address = "mm" + ("x" * 32) + "@testserver"
        result = self.send_offline_message(mm_address, self.example_user("cordelia"))
        self.assert_json_error(
            result,
            "5.1.1 Bad destination mailbox address: Zulip notification reply address is invalid.",
        )


class TestStreamEmailMessagesSubjectStripping(ZulipTestCase):
    def test_process_message_strips_subject(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)
        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("TestStreamEmailMessages body")
        incoming_valid_message["Subject"] = "Re: Fwd: Re: Test"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual("Test", message.topic_name())

        # If after stripping we get an empty subject, it should get set to (no topic)
        del incoming_valid_message["Subject"]
        incoming_valid_message["Subject"] = "Re: Fwd: Re: "
        process_message(incoming_valid_message)
        message = most_recent_message(user_profile)
        self.assertEqual("(no topic)", message.topic_name())

    def test_strip_from_subject(self) -> None:
        subject_list = orjson.loads(self.fixture_data("subjects.json", type="email"))
        for subject in subject_list:
            stripped = strip_from_subject(subject["original_subject"])
            self.assertEqual(stripped, subject["stripped_subject"])


# If the Content-Type header didn't specify a charset, the text content
# of the email used to not be properly found. Test that this is fixed:
class TestContentTypeUnspecifiedCharset(ZulipTestCase):
    def test_charset_not_specified(self) -> None:
        message_as_string = self.fixture_data("1.txt", type="email")
        message_as_string = message_as_string.replace(
            'Content-Type: text/plain; charset="us-ascii"', "Content-Type: text/plain"
        )
        incoming_message = message_from_string(message_as_string, policy=email.policy.default)
        # https://github.com/python/typeshed/issues/2417
        assert isinstance(incoming_message, EmailMessage)

        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        del incoming_message["To"]
        incoming_message["To"] = stream_to_address
        process_message(incoming_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Email fixture 1.txt body")


class TestContentTypeInvalidCharset(ZulipTestCase):
    def test_unknown_charset(self) -> None:
        message_as_string = self.fixture_data("1.txt", type="email")
        message_as_string = message_as_string.replace(
            'Content-Type: text/plain; charset="us-ascii"',
            'Content-Type: text/plain; charset="bogus"',
        )
        incoming_message = message_from_string(message_as_string, policy=email.policy.default)
        # https://github.com/python/typeshed/issues/2417
        assert isinstance(incoming_message, EmailMessage)

        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        del incoming_message["To"]
        incoming_message["To"] = stream_to_address
        process_message(incoming_message)
        message = most_recent_message(user_profile)

        self.assertEqual(message.content, "Email fixture 1.txt body")


class TestEmailMirrorProcessMessageNoValidRecipient(ZulipTestCase):
    def test_process_message_no_valid_recipient(self) -> None:
        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        incoming_valid_message["Subject"] = "Test subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = "address@wrongdomain, address@notzulip"
        incoming_valid_message["Reply-to"] = self.example_email("othello")

        with mock.patch("zerver.lib.email_mirror.log_error") as mock_log_error:
            process_message(incoming_valid_message)
            mock_log_error.assert_called_with(
                incoming_valid_message, "Missing recipient in mirror email", None
            )


class TestEmailMirrorLogAndReport(ZulipTestCase):
    def test_log_error(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "errors")
        stream = get_stream("Denmark", user_profile.realm)
        stream_to_address = encode_email_address(stream)

        incoming_valid_message = EmailMessage()
        incoming_valid_message.set_content("Test body")
        incoming_valid_message["Subject"] = "Test subject"
        incoming_valid_message["From"] = self.example_email("hamlet")
        incoming_valid_message["To"] = stream_to_address
        with self.assertLogs("zerver.lib.email_mirror", "ERROR") as error_log:
            log_error(incoming_valid_message, "test error message", stream_to_address)
        self.assertEqual(
            error_log.output,
            [
                f"ERROR:zerver.lib.email_mirror:Sender: hamlet@zulip.com\nTo: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX@testserver <Address to stream id: {stream.id}>\ntest error message"
            ],
        )

        with self.assertLogs("zerver.lib.email_mirror", "ERROR") as error_log:
            log_error(incoming_valid_message, "test error message", None)
        self.assertEqual(
            error_log.output,
            [
                "ERROR:zerver.lib.email_mirror:Sender: hamlet@zulip.com\nTo: No recipient found\ntest error message"
            ],
        )

    def test_redact_email_address(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "errors")
        stream = get_stream("Denmark", user_profile.realm)

        # Test for a stream address:
        stream_to_address = encode_email_address(stream)
        address = Address(addr_spec=stream_to_address)
        scrubbed_stream_address = Address(
            username="X" * len(address.username), domain=address.domain
        ).addr_spec

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
        expected_message = expected_message.format("XXXXXXX@testserver")

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test for a missed message address:
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "test_redact_email_message",
                "to": orjson.dumps([cordelia.email, iago.email]).decode(),
            },
        )
        self.assert_json_success(result)

        cordelia_profile = self.example_user("cordelia")
        user_message = most_recent_usermessage(cordelia_profile)
        mm_address = create_missed_message_address(user_profile, user_message.message)

        error_message = "test message {}"
        error_message = error_message.format(mm_address)
        expected_message = "test message {} <Missed message address>"
        expected_message = expected_message.format("X" * 34 + "@testserver")

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test if redacting correctly scrubs multiple occurrences of the address:
        error_message = "test message first occurrence: {} second occurrence: {}"
        error_message = error_message.format(stream_to_address, stream_to_address)
        expected_message = "test message first occurrence: {} <Address to stream id: {}>"
        expected_message += " second occurrence: {} <Address to stream id: {}>"
        expected_message = expected_message.format(
            scrubbed_stream_address, stream.id, scrubbed_stream_address, stream.id
        )

        redacted_message = redact_email_address(error_message)
        self.assertEqual(redacted_message, expected_message)

        # Test with EMAIL_GATEWAY_EXTRA_PATTERN_HACK:
        with self.settings(EMAIL_GATEWAY_EXTRA_PATTERN_HACK="@zulip.org"):
            stream_to_address = stream_to_address.replace("@testserver", "@zulip.org")
            scrubbed_stream_address = scrubbed_stream_address.replace("@testserver", "@zulip.org")
            error_message = "test message {}"
            error_message = error_message.format(stream_to_address)
            expected_message = "test message {} <Address to stream id: {}>"
            expected_message = expected_message.format(scrubbed_stream_address, stream.id)

            redacted_message = redact_email_address(error_message)
            self.assertEqual(redacted_message, expected_message)
