import random
import re
from email.headerregistry import Address
from typing import Dict, List, Optional, Sequence, Union
from unittest import mock
from unittest.mock import patch

import lxml.html
import orjson
from django.conf import settings
from django.core import mail
from django.core.mail.message import EmailMultiAlternatives
from django.test import override_settings
from django_stubs_ext import StrPromise

from zerver.actions.create_user import do_create_user
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.email_notifications import (
    MissedMessageData,
    fix_emojis,
    fix_spoilers_in_html,
    handle_missedmessage_emails,
    include_realm_name_in_missedmessage_emails_subject,
    relative_to_full_url,
)
from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserMessage, UserProfile, UserTopic
from zerver.models.realm_emoji import get_name_keyed_dict_for_active_realm_emoji
from zerver.models.realms import get_realm
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import get_stream


class TestMessageNotificationEmails(ZulipTestCase):
    def test_read_message(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login("cordelia")
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": orjson.dumps([hamlet.email]).decode(),
            },
        )
        self.assert_json_success(result)
        message = self.get_last_message()

        # The message is marked as read for the sender (Cordelia) by the message send codepath.
        # We obviously should not send notifications to someone for messages they sent themselves.
        with mock.patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip"
        ) as m:
            handle_missedmessage_emails(
                cordelia.id,
                {message.id: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE)},
            )
        m.assert_not_called()

        # If the notification is processed before Hamlet reads the message, he should get the email.
        with mock.patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip"
        ) as m:
            handle_missedmessage_emails(
                hamlet.id,
                {message.id: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE)},
            )
        m.assert_called_once()

        # If Hamlet reads the message before receiving the email notification, we should not sent him
        # an email.
        usermessage = UserMessage.objects.get(
            user_profile=hamlet,
            message=message,
        )
        usermessage.flags.read = True
        usermessage.save()
        with mock.patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip"
        ) as m:
            handle_missedmessage_emails(
                hamlet.id,
                {message.id: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE)},
            )
        m.assert_not_called()

    def normalize_string(self, s: Union[str, StrPromise]) -> str:
        s = s.strip()
        return re.sub(r"\s+", " ", s)

    def _get_tokens(self) -> List[str]:
        return ["mm" + str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(
        self,
        msg_id: int,
        verify_body_include: List[str],
        email_subject: str,
        verify_html_body: bool = False,
        show_message_content: bool = True,
        verify_body_does_not_include: Sequence[str] = [],
        trigger: str = "",
        mentioned_user_group_id: Optional[int] = None,
    ) -> None:
        hamlet = self.example_user("hamlet")
        tokens = self._get_tokens()
        with patch("zerver.lib.email_mirror.generate_missed_message_token", side_effect=tokens):
            handle_missedmessage_emails(
                hamlet.id,
                {
                    msg_id: MissedMessageData(
                        trigger=trigger, mentioned_user_group_id=mentioned_user_group_id
                    )
                },
            )
        if settings.EMAIL_GATEWAY_PATTERN != "":
            reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (t,) for t in tokens]
            reply_to_emails = [
                str(Address(display_name="Zulip", addr_spec=address))
                for address in reply_to_addresses
            ]
        else:
            reply_to_emails = ["noreply@testserver"]
        msg = mail.outbox[0]
        assert isinstance(msg, EmailMultiAlternatives)
        from_email = str(
            Address(display_name="testserver notifications", addr_spec=FromAddress.NOREPLY)
        )
        self.assert_length(mail.outbox, 1)
        self.assertEqual(self.email_envelope_from(msg), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertEqual(self.email_display_from(msg), from_email)
        self.assertEqual(msg.subject, email_subject)
        self.assert_length(msg.reply_to, 1)
        self.assertIn(msg.reply_to[0], reply_to_emails)
        if verify_html_body:
            for text in verify_body_include:
                assert isinstance(msg.alternatives[0][0], str)
                html = self.normalize_string(msg.alternatives[0][0])
                self.assertIn(text, html)
        else:
            for text in verify_body_include:
                self.assertIn(text, self.normalize_string(msg.body))
        for text in verify_body_does_not_include:
            self.assertNotIn(text, self.normalize_string(msg.body))

        self.assertEqual(msg.extra_headers["List-Id"], "Zulip Dev <zulip.testserver>")

    def _realm_name_in_missed_message_email_subject(
        self, realm_name_in_notifications: bool
    ) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )
        verify_body_include = ["Extremely personal message!"]
        email_subject = "DMs with Othello, the Moor of Venice"

        if realm_name_in_notifications:
            email_subject = "DMs with Othello, the Moor of Venice [Zulip Dev]"
        self._test_cases(msg_id, verify_body_include, email_subject)

    def _extra_context_in_missed_stream_messages_mention(
        self, show_message_content: bool = True
    ) -> None:
        for i in range(11):
            self.send_stream_message(
                self.example_user("othello"),
                "Denmark",
                content=str(i),
                topic_name="test" if i % 2 == 0 else "TEST",
            )
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(
            self.example_user("othello"), "denmark", "@**King Hamlet**"
        )

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > 1 > 2 > 3 > 4 > 5 > 6 > 7 > 8 > 9 > 10 > @**King Hamlet** -- ",
                "You are receiving this because you were personally mentioned.",
            ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/dm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]

            email_subject = "New messages"
            verify_body_does_not_include = [
                "Denmark > test",
                "Othello, the Moor of Venice",
                "1 2 3 4 5 6 7 8 9 10 @**King Hamlet**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger=NotificationTriggers.MENTION,
        )

    def _extra_context_in_missed_stream_messages_topic_wildcard_mention_in_followed_topic(
        self,
        show_message_content: bool = True,
        *,
        receiver_is_participant: bool,
    ) -> None:
        for i in range(1, 3):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")

        if receiver_is_participant:
            self.send_stream_message(self.example_user("hamlet"), "Denmark", content="hello")

        msg_id = self.send_stream_message(self.example_user("othello"), "Denmark", "@**topic**")
        trigger = NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        if not receiver_is_participant:
            trigger = NotificationTriggers.STREAM_EMAIL

        if show_message_content:
            # If Hamlet (receiver) is not a topic participant, @topic doesn't mention him,
            # so he won't receive added context (previous messages) in the email.
            if receiver_is_participant:
                verify_body_include = [
                    "Othello, the Moor of Venice: > 1 > 2 King Hamlet: > hello Othello, the Moor of Venice: > @**topic** -- ",
                    "You are receiving this because all topic participants were mentioned in #Denmark > test.",
                ]
            else:
                verify_body_include = [
                    "Othello, the Moor of Venice: > @**topic** -- ",
                    "You are receiving this because you have email notifications enabled for #Denmark.",
                ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/dm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Othello, the Moor of Venice",
                "1 2 3 4 5 @**topic**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger=trigger,
        )

    def _extra_context_in_missed_stream_messages_stream_wildcard_mention_in_followed_topic(
        self, show_message_content: bool = True
    ) -> None:
        for i in range(1, 6):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(self.example_user("othello"), "Denmark", "@**all**")

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > 1 > 2 > 3 > 4 > 5 > @**all** -- ",
                "You are receiving this because you have wildcard mention notifications enabled for topics you follow.",
            ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/dm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Denmark > test",
                "Othello, the Moor of Venice",
                "1 2 3 4 5 @**all**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger=NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
        )

    def _extra_context_in_missed_stream_messages_topic_wildcard_mention(
        self,
        show_message_content: bool = True,
        *,
        receiver_is_participant: bool,
    ) -> None:
        for i in range(1, 3):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")

        if receiver_is_participant:
            self.send_stream_message(self.example_user("hamlet"), "Denmark", content="hello")

        msg_id = self.send_stream_message(self.example_user("othello"), "denmark", "@**topic**")
        trigger = NotificationTriggers.TOPIC_WILDCARD_MENTION
        if not receiver_is_participant:
            trigger = NotificationTriggers.STREAM_EMAIL

        if show_message_content:
            # If Hamlet (receiver) is not a topic participant, @topic doesn't mention him,
            # so he won't receive added context (previous messages) in the email.
            if receiver_is_participant:
                verify_body_include = [
                    "Othello, the Moor of Venice: > 1 > 2 King Hamlet: > hello Othello, the Moor of Venice: > @**topic** -- ",
                    "You are receiving this because all topic participants were mentioned in #Denmark > test.",
                ]
            else:
                verify_body_include = [
                    "Othello, the Moor of Venice: > @**topic** -- ",
                    "You are receiving this because you have email notifications enabled for #Denmark.",
                ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/dm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Othello, the Moor of Venice",
                "1 2 3 4 5 @**topic**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger=trigger,
        )

    def _extra_context_in_missed_stream_messages_stream_wildcard_mention(
        self, show_message_content: bool = True
    ) -> None:
        for i in range(1, 6):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(self.example_user("othello"), "denmark", "@**all**")

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > 1 > 2 > 3 > 4 > 5 > @**all** -- ",
                "You are receiving this because everyone was mentioned in #Denmark.",
            ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/dm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Denmark > test",
                "Othello, the Moor of Venice",
                "1 2 3 4 5 @**all**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger=NotificationTriggers.STREAM_WILDCARD_MENTION,
        )

    def _extra_context_in_missed_stream_messages_email_notify(self) -> None:
        for i in range(11):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(self.example_user("othello"), "denmark", "12")
        verify_body_include = [
            "Othello, the Moor of Venice: > 12 -- ",
            "You are receiving this because you have email notifications enabled for #Denmark.",
        ]
        email_subject = "#Denmark > test"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            trigger=NotificationTriggers.STREAM_EMAIL,
        )

    def _extra_context_in_missed_stream_messages_mention_two_senders(
        self,
    ) -> None:
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, "Denmark")

        for i in range(3):
            self.send_stream_message(cordelia, "Denmark", str(i))
        msg_id = self.send_stream_message(
            self.example_user("othello"), "Denmark", "@**King Hamlet**"
        )
        verify_body_include = [
            "Cordelia, Lear's daughter: > 0 > 1 > 2 Othello, the Moor of Venice: > @**King Hamlet** -- ",
            "You are receiving this because you were personally mentioned.",
        ]
        email_subject = "#Denmark > test"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            trigger=NotificationTriggers.MENTION,
        )

    def _resolved_topic_missed_stream_messages_thread_friendly(self) -> None:
        topic_name = "threading and so forth"
        othello_user = self.example_user("othello")
        msg_id = -1
        for i in range(3):
            msg_id = self.send_stream_message(
                othello_user,
                "Denmark",
                content=str(i),
                topic_name=topic_name,
            )

        self.assert_json_success(self.resolve_topic_containing_message(othello_user, msg_id))

        verify_body_include = [
            "Othello, the Moor of Venice: > 2 -- ",
            "You are receiving this because you have email notifications enabled for #Denmark.",
        ]
        email_subject = "[resolved] #Denmark > threading and so forth"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            trigger=NotificationTriggers.STREAM_EMAIL,
        )

    def _extra_context_in_missed_personal_messages(
        self,
        show_message_content: bool = True,
        message_content_disabled_by_user: bool = False,
        message_content_disabled_by_realm: bool = False,
    ) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )

        if show_message_content:
            verify_body_include = ["> Extremely personal message!"]
            email_subject = "DMs with Othello, the Moor of Venice"
            verify_body_does_not_include: List[str] = []
        else:
            if message_content_disabled_by_realm:
                verify_body_include = [
                    "This email does not include message content because your organization has disabled",
                    "http://zulip.testserver/help/hide-message-content-in-emails",
                    "View or reply in Zulip Dev Zulip",
                    " Manage email preferences: http://zulip.testserver/#settings/notifications",
                ]
            elif message_content_disabled_by_user:
                verify_body_include = [
                    "This email does not include message content because you have disabled message ",
                    "http://zulip.testserver/help/dm-mention-alert-notifications ",
                    "View or reply in Zulip Dev Zulip",
                    " Manage email preferences: http://zulip.testserver/#settings/notifications",
                ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Othello, the Moor of Venice",
                "Extremely personal message!",
                "mentioned",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
        )

    def _reply_to_email_in_missed_personal_messages(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )
        verify_body_include = ["Reply to this email directly, or view it in Zulip Dev Zulip"]
        email_subject = "DMs with Othello, the Moor of Venice"
        self._test_cases(msg_id, verify_body_include, email_subject)

    def _reply_warning_in_missed_personal_messages(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )
        verify_body_include = ["Do not reply to this email."]
        email_subject = "DMs with Othello, the Moor of Venice"
        self._test_cases(msg_id, verify_body_include, email_subject)

    def _extra_context_in_missed_huddle_messages_two_others(
        self, show_message_content: bool = True
    ) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
            ],
            "Group personal message!",
        )

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > Group personal message! -- Reply"
            ]
            email_subject = "Group DMs with Iago and Othello, the Moor of Venice"
            verify_body_does_not_include: List[str] = []
        else:
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/dm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Iago",
                "Othello, the Moor of Venice Othello, the Moor of Venice",
                "Group personal message!",
                "mentioned",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
        )

    def _extra_context_in_missed_huddle_messages_three_others(self) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
                self.example_user("cordelia"),
            ],
            "Group personal message!",
        )

        verify_body_include = ["Othello, the Moor of Venice: > Group personal message! -- Reply"]
        email_subject = (
            "Group DMs with Cordelia, Lear's daughter, Iago, and Othello, the Moor of Venice"
        )
        self._test_cases(msg_id, verify_body_include, email_subject)

    def _extra_context_in_missed_huddle_messages_many_others(self) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
                self.example_user("cordelia"),
                self.example_user("prospero"),
            ],
            "Group personal message!",
        )

        verify_body_include = ["Othello, the Moor of Venice: > Group personal message! -- Reply"]
        email_subject = "Group DMs with Cordelia, Lear's daughter, Iago, and 2 others"
        self._test_cases(msg_id, verify_body_include, email_subject)

    def _deleted_message_in_missed_stream_messages(self) -> None:
        msg_id = self.send_stream_message(
            self.example_user("othello"), "denmark", "@**King Hamlet** to be deleted"
        )

        hamlet = self.example_user("hamlet")
        self.login("othello")
        result = self.client_patch("/json/messages/" + str(msg_id), {"content": " "})
        self.assert_json_success(result)
        handle_missedmessage_emails(
            hamlet.id, {msg_id: MissedMessageData(trigger=NotificationTriggers.MENTION)}
        )
        self.assert_length(mail.outbox, 0)

    def _deleted_message_in_missed_personal_messages(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message! to be deleted!",
        )

        hamlet = self.example_user("hamlet")
        self.login("othello")
        result = self.client_patch("/json/messages/" + str(msg_id), {"content": " "})
        self.assert_json_success(result)
        handle_missedmessage_emails(
            hamlet.id, {msg_id: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE)}
        )
        self.assert_length(mail.outbox, 0)

    def _deleted_message_in_missed_huddle_messages(self) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
            ],
            "Group personal message!",
        )

        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.login("othello")
        result = self.client_patch("/json/messages/" + str(msg_id), {"content": " "})
        self.assert_json_success(result)
        handle_missedmessage_emails(
            hamlet.id, {msg_id: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE)}
        )
        self.assert_length(mail.outbox, 0)
        handle_missedmessage_emails(
            iago.id, {msg_id: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE)}
        )
        self.assert_length(mail.outbox, 0)

    def test_smaller_user_group_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        hamlet_only = check_add_user_group(
            get_realm("zulip"), "hamlet_only", [hamlet], acting_user=None
        )
        hamlet_and_cordelia = check_add_user_group(
            get_realm("zulip"), "hamlet_and_cordelia", [hamlet, cordelia], acting_user=None
        )

        hamlet_only_message_id = self.send_stream_message(othello, "Denmark", "@*hamlet_only*")
        hamlet_and_cordelia_message_id = self.send_stream_message(
            othello, "Denmark", "@*hamlet_and_cordelia*"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                hamlet_only_message_id: MissedMessageData(
                    trigger=NotificationTriggers.MENTION, mentioned_user_group_id=hamlet_only.id
                ),
                hamlet_and_cordelia_message_id: MissedMessageData(
                    trigger=NotificationTriggers.MENTION,
                    mentioned_user_group_id=hamlet_and_cordelia.id,
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @*hamlet_only* > @*hamlet_and_cordelia* -- ",
            "You are receiving this because @hamlet_only was mentioned.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_personal_over_user_group_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        hamlet_and_cordelia = check_add_user_group(
            get_realm("zulip"), "hamlet_and_cordelia", [hamlet, cordelia], acting_user=None
        )

        user_group_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@*hamlet_and_cordelia*"
        )
        personal_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@**King Hamlet**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                user_group_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.MENTION,
                    mentioned_user_group_id=hamlet_and_cordelia.id,
                ),
                personal_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.MENTION
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @*hamlet_and_cordelia* > @**King Hamlet** -- ",
            "You are receiving this because you were personally mentioned.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_user_group_over_topic_wildcard_mention_in_followed_topic_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        hamlet_and_cordelia = check_add_user_group(
            get_realm("zulip"), "hamlet_and_cordelia", [hamlet, cordelia], acting_user=None
        )

        topic_wildcard_mentioned_in_followed_topic_message_id = self.send_stream_message(
            othello, "Denmark", "@**topic**"
        )
        user_group_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@*hamlet_and_cordelia*"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                topic_wildcard_mentioned_in_followed_topic_message_id: MissedMessageData(
                    trigger=NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
                ),
                user_group_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.MENTION,
                    mentioned_user_group_id=hamlet_and_cordelia.id,
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @**topic** > @*hamlet_and_cordelia* -- ",
            "You are receiving this because @hamlet_and_cordelia was mentioned.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_topic_wildcard_in_followed_topic_over_stream_wildcard_mention_in_followed_topic_priority(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream_wildcard_mentioned_in_followed_topic_message_id = self.send_stream_message(
            othello, "Denmark", "@**all**"
        )
        topic_wildcard_mentioned_in_followed_topic_message_id = self.send_stream_message(
            othello, "Denmark", "@**topic**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                stream_wildcard_mentioned_in_followed_topic_message_id: MissedMessageData(
                    trigger=NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
                ),
                topic_wildcard_mentioned_in_followed_topic_message_id: MissedMessageData(
                    trigger=NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @**all** > @**topic** -- ",
            "You are receiving this because all topic participants were mentioned in #Denmark > test.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_stream_wildcard_in_followed_topic_over_topic_wildcard_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        topic_wildcard_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@**topic**"
        )
        stream_wildcard_mentioned_in_followed_topic_message_id = self.send_stream_message(
            othello, "Denmark", "@**all**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                topic_wildcard_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.TOPIC_WILDCARD_MENTION
                ),
                stream_wildcard_mentioned_in_followed_topic_message_id: MissedMessageData(
                    trigger=NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @**topic** > @**all** -- ",
            "You are receiving this because you have wildcard mention notifications enabled for topics you follow.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_topic_wildcard_over_stream_wildcard_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream_wildcard_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@**all**"
        )
        topic_wildcard_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@**topic**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                stream_wildcard_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.STREAM_WILDCARD_MENTION
                ),
                topic_wildcard_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.TOPIC_WILDCARD_MENTION
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @**all** > @**topic** -- ",
            "You are receiving this because all topic participants were mentioned in #Denmark > test.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_stream_wildcard_mention_over_followed_topic_notify_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        followed_topic_mentioned_message_id = self.send_stream_message(othello, "Denmark", "1")
        stream_wildcard_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@**all**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                followed_topic_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.FOLLOWED_TOPIC_EMAIL
                ),
                stream_wildcard_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.STREAM_WILDCARD_MENTION
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > 1 > @**all** -- ",
            "You are receiving this because everyone was mentioned in #Denmark.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_followed_topic_notify_over_stream_message_notify_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", "0")
        followed_topic_mentioned_message_id = self.send_stream_message(othello, "Denmark", "1")

        handle_missedmessage_emails(
            hamlet.id,
            {
                stream_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.STREAM_EMAIL
                ),
                followed_topic_mentioned_message_id: MissedMessageData(
                    trigger=NotificationTriggers.FOLLOWED_TOPIC_EMAIL
                ),
            },
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > 0 > 1 -- ",
            "You are receiving this because you have email notifications enabled for topics you follow.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_include_realm_name_in_missedmessage_emails_subject(self) -> None:
        user = self.example_user("hamlet")

        # Test with 'realm_name_in_notification_policy' set to 'Always'
        do_change_user_setting(
            user,
            "realm_name_in_email_notifications_policy",
            UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_ALWAYS,
            acting_user=None,
        )
        self.assertTrue(include_realm_name_in_missedmessage_emails_subject(user))

        # Test with 'realm_name_in_notification_policy' set to 'Never'
        do_change_user_setting(
            user,
            "realm_name_in_email_notifications_policy",
            UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_NEVER,
            acting_user=None,
        )
        self.assertFalse(include_realm_name_in_missedmessage_emails_subject(user))

        # Test with 'realm_name_in_notification_policy' set to 'Automatic'
        do_change_user_setting(
            user,
            "realm_name_in_email_notifications_policy",
            UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_AUTOMATIC,
            acting_user=None,
        )
        # Case 1: if user is part of a single realm, then realm_name is not present in notifications.
        self.assertFalse(include_realm_name_in_missedmessage_emails_subject(user))

        # Case 2: if user is part of multiple realms, then realm_name should be present in notifications.
        # Create and verify a cross realm user.
        cross_realm_user = do_create_user(
            user.delivery_email, None, get_realm("lear"), user.full_name, acting_user=None
        )
        self.assertEqual(cross_realm_user.delivery_email, user.delivery_email)

        self.assertTrue(include_realm_name_in_missedmessage_emails_subject(cross_realm_user))

    def test_realm_name_in_email_notifications_policy(self) -> None:
        # Test with realm_name_in_email_notifications_policy set to Never.
        hamlet = self.example_user("hamlet")
        hamlet.realm_name_in_email_notifications_policy = (
            UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_NEVER
        )
        hamlet.save(update_fields=["realm_name_in_email_notifications_policy"])
        with mock.patch(
            "zerver.lib.email_notifications.include_realm_name_in_missedmessage_emails_subject",
            return_value=False,
        ):
            is_allowed = include_realm_name_in_missedmessage_emails_subject(hamlet)
            self._realm_name_in_missed_message_email_subject(is_allowed)

        # Test with realm_name_in_email_notifications_policy set to Always.

        # Note: We don't need to test separately for 'realm_name_in_email_notifications_policy'
        # set to 'Automatic'.
        # Here, we are concerned about the subject after the mocked function returns True/False.
        # We already have separate test to check the appropriate behaviour of
        # 'include_realm_name_in_missedmessage_emails_subject' for Automatic, Always, Never.
        hamlet = self.example_user("hamlet")
        hamlet.realm_name_in_email_notifications_policy = (
            UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_ALWAYS
        )
        hamlet.save(update_fields=["realm_name_in_email_notifications_policy"])
        with mock.patch(
            "zerver.lib.email_notifications.include_realm_name_in_missedmessage_emails_subject",
            return_value=True,
        ):
            is_allowed = include_realm_name_in_missedmessage_emails_subject(hamlet)
            # Empty the test outbox
            mail.outbox = []
            self._realm_name_in_missed_message_email_subject(is_allowed)

    def test_message_content_disabled_in_missed_message_notifications(self) -> None:
        # Test when user disabled message content in email notifications.
        do_change_user_setting(
            self.example_user("hamlet"),
            "message_content_in_email_notifications",
            False,
            acting_user=None,
        )
        self._extra_context_in_missed_stream_messages_mention(show_message_content=False)
        mail.outbox = []
        self._extra_context_in_missed_stream_messages_topic_wildcard_mention_in_followed_topic(
            show_message_content=False,
            receiver_is_participant=True,
        )
        mail.outbox = []
        self._extra_context_in_missed_stream_messages_stream_wildcard_mention_in_followed_topic(
            show_message_content=False
        )
        mail.outbox = []
        self._extra_context_in_missed_stream_messages_topic_wildcard_mention(
            show_message_content=False,
            receiver_is_participant=True,
        )
        mail.outbox = []
        self._extra_context_in_missed_stream_messages_stream_wildcard_mention(
            show_message_content=False
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            show_message_content=False, message_content_disabled_by_user=True
        )
        mail.outbox = []
        self._extra_context_in_missed_huddle_messages_two_others(show_message_content=False)

    def test_extra_context_in_missed_stream_messages(self) -> None:
        self._extra_context_in_missed_stream_messages_mention()

    def test_extra_context_in_missed_stream_messages_topic_wildcard_in_followed_topic(
        self,
    ) -> None:
        self._extra_context_in_missed_stream_messages_topic_wildcard_mention_in_followed_topic(
            receiver_is_participant=True
        )

    def test_extra_context_in_missed_stream_messages_topic_wildcard_in_followed_topic_receiver_not_participant(
        self,
    ) -> None:
        self._extra_context_in_missed_stream_messages_topic_wildcard_mention_in_followed_topic(
            receiver_is_participant=False
        )

    def test_extra_context_in_missed_stream_messages_stream_wildcard_in_followed_topic(
        self,
    ) -> None:
        self._extra_context_in_missed_stream_messages_stream_wildcard_mention_in_followed_topic()

    def test_extra_context_in_missed_stream_messages_topic_wildcard(self) -> None:
        self._extra_context_in_missed_stream_messages_topic_wildcard_mention(
            receiver_is_participant=True
        )

    def test_extra_context_in_missed_stream_messages_topic_wildcard_receiver_not_participant(
        self,
    ) -> None:
        self._extra_context_in_missed_stream_messages_topic_wildcard_mention(
            receiver_is_participant=False
        )

    def test_extra_context_in_missed_stream_messages_stream_wildcard(self) -> None:
        self._extra_context_in_missed_stream_messages_stream_wildcard_mention()

    def test_extra_context_in_missed_stream_messages_two_senders(self) -> None:
        self._extra_context_in_missed_stream_messages_mention_two_senders()

    def test_reply_to_email_in_missed_personal_messages(self) -> None:
        self._reply_to_email_in_missed_personal_messages()

    def test_extra_context_in_missed_stream_messages_email_notify(self) -> None:
        self._extra_context_in_missed_stream_messages_email_notify()

    def test_resolved_topic_missed_stream_messages_thread_friendly(self) -> None:
        self._resolved_topic_missed_stream_messages_thread_friendly()

    @override_settings(EMAIL_GATEWAY_PATTERN="")
    def test_reply_warning_in_missed_personal_messages(self) -> None:
        self._reply_warning_in_missed_personal_messages()

    def test_extra_context_in_missed_personal_messages(self) -> None:
        self._extra_context_in_missed_personal_messages()

    def test_extra_context_in_missed_huddle_messages_two_others(self) -> None:
        self._extra_context_in_missed_huddle_messages_two_others()

    def test_extra_context_in_missed_huddle_messages_three_others(self) -> None:
        self._extra_context_in_missed_huddle_messages_three_others()

    def test_extra_context_in_missed_huddle_messages_many_others(self) -> None:
        self._extra_context_in_missed_huddle_messages_many_others()

    def test_deleted_message_in_missed_stream_messages(self) -> None:
        self._deleted_message_in_missed_stream_messages()

    def test_deleted_message_in_missed_personal_messages(self) -> None:
        self._deleted_message_in_missed_personal_messages()

    def test_deleted_message_in_missed_huddle_messages(self) -> None:
        self._deleted_message_in_missed_huddle_messages()

    def test_realm_message_content_allowed_in_email_notifications(self) -> None:
        user = self.example_user("hamlet")

        # When message content is allowed at realm level
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = True
        realm.save(update_fields=["message_content_allowed_in_email_notifications"])

        # Emails have missed message content when message content is enabled by the user
        do_change_user_setting(
            user, "message_content_in_email_notifications", True, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(show_message_content=True)

        # Emails don't have missed message content when message content is disabled by the user
        do_change_user_setting(
            user, "message_content_in_email_notifications", False, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            show_message_content=False, message_content_disabled_by_user=True
        )

        # When message content is not allowed at realm level
        # Emails don't have message content irrespective of message content setting of the user
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = False
        realm.save(update_fields=["message_content_allowed_in_email_notifications"])

        do_change_user_setting(
            user, "message_content_in_email_notifications", True, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            show_message_content=False, message_content_disabled_by_realm=True
        )

        do_change_user_setting(
            user, "message_content_in_email_notifications", False, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            show_message_content=False,
            message_content_disabled_by_user=True,
            message_content_disabled_by_realm=True,
        )

    def test_realm_emoji_in_missed_message(self) -> None:
        realm = get_realm("zulip")

        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message with a realm emoji :green_tick:!",
        )
        realm_emoji_dict = get_name_keyed_dict_for_active_realm_emoji(realm.id)
        realm_emoji_id = realm_emoji_dict["green_tick"]["id"]
        realm_emoji_url = (
            f"http://zulip.testserver/user_avatars/{realm.id}/emoji/images/{realm_emoji_id}.png"
        )
        verify_body_include = [
            f'<img alt=":green_tick:" src="{realm_emoji_url}" title="green tick" style="height: 20px;">'
        ]
        email_subject = "DMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            verify_html_body=True,
        )

    def test_emojiset_in_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.emojiset = "twitter"
        hamlet.save(update_fields=["emojiset"])
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message with a hamburger :hamburger:!",
        )
        verify_body_include = [
            '<img alt=":hamburger:" src="http://testserver/static/generated/emoji/images-twitter-64/1f354.png" title="hamburger" style="height: 20px;">'
        ]
        email_subject = "DMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            verify_html_body=True,
        )

    def test_stream_link_in_missed_message(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Come and join us in #**Verona**.",
        )
        stream_id = get_stream("Verona", get_realm("zulip")).id
        href = f"http://zulip.testserver/#narrow/stream/{stream_id}-Verona"
        verify_body_include = [
            f'<a class="stream" href="{href}" data-stream-id="{stream_id}">#Verona</a'
        ]
        email_subject = "DMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            verify_html_body=True,
        )

    def test_pm_link_in_missed_message_header(self) -> None:
        cordelia = self.example_user("cordelia")
        msg_id = self.send_personal_message(
            cordelia,
            self.example_user("hamlet"),
            "Let's test a direct message link in email notifications",
        )

        encoded_name = "Cordelia,-Lear's-daughter"
        verify_body_include = [
            f"view it in Zulip Dev Zulip: http://zulip.testserver/#narrow/dm/{cordelia.id}-{encoded_name}"
        ]
        email_subject = "DMs with Cordelia, Lear's daughter"
        self._test_cases(msg_id, verify_body_include, email_subject)

    def test_sender_name_in_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(
            self.example_user("iago"), "Denmark", "@**King Hamlet**"
        )
        msg_id_2 = self.send_stream_message(self.example_user("iago"), "Verona", "* 1\n *2")
        msg_id_3 = self.send_personal_message(self.example_user("iago"), hamlet, "Hello")

        handle_missedmessage_emails(
            hamlet.id,
            {
                msg_id_1: MissedMessageData(trigger=NotificationTriggers.MENTION),
                msg_id_2: MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL),
                msg_id_3: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE),
            },
        )

        assert isinstance(mail.outbox[0], EmailMultiAlternatives)
        assert isinstance(mail.outbox[0].alternatives[0][0], str)
        self.assertIn("Iago:\n> @**King Hamlet**\n\n--\nYou are", mail.outbox[0].body)
        # If message content starts with <p> tag the sender name is appended inside the <p> tag.
        self.assertIn(
            '<p><b>Iago</b>: <span class="user-mention"',
            mail.outbox[0].alternatives[0][0],
        )

        assert isinstance(mail.outbox[1], EmailMultiAlternatives)
        assert isinstance(mail.outbox[1].alternatives[0][0], str)
        self.assertIn("Iago:\n> * 1\n>  *2\n\n--\nYou are receiving", mail.outbox[1].body)
        # If message content does not starts with <p> tag sender name is appended before the <p> tag
        self.assertIn(
            "       <b>Iago</b>: <div><ul>\n<li>1<br>\n *2</li>\n</ul></div>\n",
            mail.outbox[1].alternatives[0][0],
        )

        assert isinstance(mail.outbox[2], EmailMultiAlternatives)
        assert isinstance(mail.outbox[2].alternatives[0][0], str)
        self.assertEqual("> Hello\n\n--\n\nReply", mail.outbox[2].body[:18])
        # Sender name is not appended to message for missed direct messages
        self.assertIn(
            ">\n                    \n                        <div><p>Hello</p></div>\n",
            mail.outbox[2].alternatives[0][0],
        )

    def test_multiple_missed_personal_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_personal_message(
            self.example_user("othello"), hamlet, "Personal Message 1"
        )
        msg_id_2 = self.send_personal_message(
            self.example_user("iago"), hamlet, "Personal Message 2"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                msg_id_1: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE),
                msg_id_2: MissedMessageData(trigger=NotificationTriggers.DIRECT_MESSAGE),
            },
        )
        self.assert_length(mail.outbox, 2)
        email_subject = "DMs with Othello, the Moor of Venice"
        self.assertEqual(mail.outbox[0].subject, email_subject)
        email_subject = "DMs with Iago"
        self.assertEqual(mail.outbox[1].subject, email_subject)

    def test_multiple_stream_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        message_ids: Dict[int, MissedMessageData] = {}
        for i in range(1, 4):
            msg_id = self.send_stream_message(othello, "Denmark", content=str(i))
            message_ids[msg_id] = MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL)
        for i in range(4, 7):
            msg_id = self.send_stream_message(iago, "Denmark", content=str(i))
            message_ids[msg_id] = MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL)

        handle_missedmessage_emails(
            hamlet.id,
            message_ids,
        )

        email_subject = "#Denmark > test"
        verify_body_include = [
            "Othello, the Moor of Venice: > 1 > 2 > 3 Iago: > 4 > 5 > 6 -- ",
            "You are receiving this because you have email notifications enabled for #Denmark.",
        ]
        self.assert_length(mail.outbox, 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, email_subject)
        for text in verify_body_include:
            self.assertIn(text, self.normalize_string(msg.body))

    def test_multiple_stream_messages_and_mentions(self) -> None:
        """Subject should be stream name and topic as usual."""
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(self.example_user("iago"), "Denmark", "Regular message")
        msg_id_2 = self.send_stream_message(
            self.example_user("othello"), "Denmark", "@**King Hamlet**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                msg_id_1: MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL),
                msg_id_2: MissedMessageData(trigger=NotificationTriggers.MENTION),
            },
        )
        self.assert_length(mail.outbox, 1)
        email_subject = "#Denmark > test"
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_message_access_in_emails(self) -> None:
        # Messages sent to a protected history-private stream shouldn't be
        # accessible/available in emails before subscribing
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True, history_public_to_subscribers=False)
        user = self.example_user("iago")
        self.subscribe(user, stream_name)
        late_subscribed_user = self.example_user("hamlet")

        self.send_stream_message(user, stream_name, "Before subscribing")

        self.subscribe(late_subscribed_user, stream_name)

        self.send_stream_message(user, stream_name, "After subscribing")

        mention_msg_id = self.send_stream_message(user, stream_name, "@**King Hamlet**")

        handle_missedmessage_emails(
            late_subscribed_user.id,
            {mention_msg_id: MissedMessageData(trigger=NotificationTriggers.MENTION)},
        )

        self.assert_length(mail.outbox, 1)
        self.assertEqual(mail.outbox[0].subject, "#private_stream > test")  # email subject
        email_text = mail.outbox[0].message().as_string()
        self.assertNotIn("Before subscribing", email_text)
        self.assertIn("After subscribing", email_text)
        self.assertIn("@**King Hamlet**", email_text)

    def test_stream_mentions_multiple_people(self) -> None:
        """Subject should be stream name and topic as usual."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        self.subscribe(cordelia, "Denmark")

        msg_id_1 = self.send_stream_message(
            self.example_user("iago"), "Denmark", "@**King Hamlet**"
        )
        msg_id_2 = self.send_stream_message(
            self.example_user("othello"), "Denmark", "@**King Hamlet**"
        )
        msg_id_3 = self.send_stream_message(cordelia, "Denmark", "Regular message")

        handle_missedmessage_emails(
            hamlet.id,
            {
                msg_id_1: MissedMessageData(trigger=NotificationTriggers.MENTION),
                msg_id_2: MissedMessageData(trigger=NotificationTriggers.MENTION),
                msg_id_3: MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL),
            },
        )
        self.assert_length(mail.outbox, 1)
        email_subject = "#Denmark > test"
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_multiple_stream_messages_different_topics(self) -> None:
        """Should receive separate emails for each topic within a stream."""
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(self.example_user("othello"), "Denmark", "Message1")
        msg_id_2 = self.send_stream_message(
            self.example_user("iago"), "Denmark", "Message2", topic_name="test2"
        )

        handle_missedmessage_emails(
            hamlet.id,
            {
                msg_id_1: MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL),
                msg_id_2: MissedMessageData(trigger=NotificationTriggers.STREAM_EMAIL),
            },
        )
        self.assert_length(mail.outbox, 2)
        email_subjects = {mail.outbox[0].subject, mail.outbox[1].subject}
        valid_email_subjects = {"#Denmark > test", "#Denmark > test2"}
        self.assertEqual(email_subjects, valid_email_subjects)

    def test_relative_to_full_url(self) -> None:
        def convert(test_data: str) -> str:
            fragment = lxml.html.fragment_fromstring(test_data, create_parent=True)
            relative_to_full_url(fragment, "http://example.com")
            return lxml.html.tostring(fragment, encoding="unicode")

        zulip_realm = get_realm("zulip")
        zephyr_realm = get_realm("zephyr")
        # Run `relative_to_full_url()` function over test fixtures present in
        # 'markdown_test_cases.json' and check that it converts all the relative
        # URLs to absolute URLs.
        fixtures = orjson.loads(self.fixture_data("markdown_test_cases.json"))
        test_fixtures = {}
        for test in fixtures["regular_tests"]:
            test_fixtures[test["name"]] = test
        for test_name in test_fixtures:
            test_data = test_fixtures[test_name]["expected_output"]
            output_data = convert(test_data)
            if re.search(r"""(?<=\=['"])/(?=[^<]+>)""", output_data) is not None:
                raise AssertionError(
                    "Relative URL present in email: "
                    + output_data
                    + "\nFailed test case's name is: "
                    + test_name
                    + "\nIt is present in markdown_test_cases.json"
                )

        # Specific test cases.

        # A path similar to our emoji path, but not in a link:
        test_data = "<p>Check out the file at: '/static/generated/emoji/images/emoji/'</p>"
        actual_output = convert(test_data)
        expected_output = (
            "<div><p>Check out the file at: '/static/generated/emoji/images/emoji/'</p></div>"
        )
        self.assertEqual(actual_output, expected_output)

        # An uploaded file
        test_data = '<a href="/user_uploads/{realm_id}/1f/some_random_value">/user_uploads/{realm_id}/1f/some_random_value</a>'
        test_data = test_data.format(realm_id=zephyr_realm.id)
        actual_output = convert(test_data)
        expected_output = (
            '<div><a href="http://example.com/user_uploads/{realm_id}/1f/some_random_value">'
            "/user_uploads/{realm_id}/1f/some_random_value</a></div>"
        )
        expected_output = expected_output.format(realm_id=zephyr_realm.id)
        self.assertEqual(actual_output, expected_output)

        # A profile picture like syntax, but not actually in an HTML tag
        test_data = '<p>Set src="/avatar/username@example.com?s=30"</p>'
        actual_output = convert(test_data)
        expected_output = '<div><p>Set src="/avatar/username@example.com?s=30"</p></div>'
        self.assertEqual(actual_output, expected_output)

        # A narrow URL which begins with a '#'.
        test_data = (
            '<p><a href="#narrow/stream/test/topic/test.20topic/near/142"'
            ' title="#narrow/stream/test/topic/test.20topic/near/142">Conversation</a></p>'
        )
        actual_output = convert(test_data)
        expected_output = (
            '<div><p><a href="http://example.com/#narrow/stream/test/topic/test.20topic/near/142"'
            ' title="http://example.com/#narrow/stream/test/topic/test.20topic/near/142">Conversation</a></p></div>'
        )
        self.assertEqual(actual_output, expected_output)

        # Scrub inline images.
        test_data = (
            "<p>See this <a"
            ' href="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"'
            ' target="_blank" title="avatar_103.jpeg">avatar_103.jpeg</a>.</p>'
            '<div class="message_inline_image"><a'
            ' href="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"'
            ' target="_blank" title="avatar_103.jpeg"><img'
            ' src="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"></a></div>'
        )
        test_data = test_data.format(realm_id=zulip_realm.id)
        actual_output = convert(test_data)
        expected_output = (
            "<div><p>See this <a"
            ' href="http://example.com/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"'
            ' target="_blank" title="avatar_103.jpeg">avatar_103.jpeg</a>.</p></div>'
        )
        expected_output = expected_output.format(realm_id=zulip_realm.id)
        self.assertEqual(actual_output, expected_output)

        # A message containing only an inline image URL preview, we do
        # somewhat more extensive surgery.
        test_data = (
            '<div class="message_inline_image"><a'
            ' href="https://www.google.com/images/srpr/logo4w.png"'
            ' target="_blank" title="https://www.google.com/images/srpr/logo4w.png">'
            '<img data-src-fullsize="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x0"'
            ' src="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x100"></a></div>'
        )
        actual_output = convert(test_data)
        expected_output = (
            '<div><p><a href="https://www.google.com/images/srpr/logo4w.png"'
            ' target="_blank" title="https://www.google.com/images/srpr/logo4w.png">'
            "https://www.google.com/images/srpr/logo4w.png</a></p></div>"
        )
        self.assertEqual(actual_output, expected_output)

    def test_spoilers_in_html_emails(self) -> None:
        test_data = '<div class="spoiler-block"><div class="spoiler-header">\n\n<p><a>header</a> text</p>\n</div><div class="spoiler-content" aria-hidden="true">\n\n<p>content</p>\n</div></div>\n\n<p>outside spoiler</p>'
        fragment = lxml.html.fromstring(test_data)
        fix_spoilers_in_html(fragment, "en")
        actual_output = lxml.html.tostring(fragment, encoding="unicode")
        expected_output = '<div><div class="spoiler-block">\n\n<p><a>header</a> text <span class="spoiler-title" title="Open Zulip to see the spoiler content">(Open Zulip to see the spoiler content)</span></p>\n</div>\n\n<p>outside spoiler</p></div>'
        self.assertEqual(actual_output, expected_output)

        # test against our markdown_test_cases so these features do not get out of sync.
        fixtures = orjson.loads(self.fixture_data("markdown_test_cases.json"))
        test_fixtures = {}
        for test in fixtures["regular_tests"]:
            if "spoiler" in test["name"]:
                test_fixtures[test["name"]] = test
        for test_name in test_fixtures:
            fragment = lxml.html.fromstring(test_fixtures[test_name]["expected_output"])
            fix_spoilers_in_html(fragment, "en")
            output_data = lxml.html.tostring(fragment, encoding="unicode")
            assert "spoiler-header" not in output_data
            assert "spoiler-content" not in output_data
            assert "spoiler-block" in output_data
            assert "spoiler-title" in output_data

    def test_spoilers_in_text_emails(self) -> None:
        content = "@**King Hamlet**\n\n```spoiler header text\nsecret-text\n```"
        msg_id = self.send_stream_message(self.example_user("othello"), "Denmark", content)
        verify_body_include = ["header text", "Open Zulip to see the spoiler content"]
        verify_body_does_not_include = ["secret-text"]
        email_subject = "#Denmark > test"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            trigger=NotificationTriggers.MENTION,
            verify_body_does_not_include=verify_body_does_not_include,
        )

    def test_fix_emoji(self) -> None:
        # An emoji.
        test_data = (
            '<p>See <span aria-label="cloud with lightning and rain" class="emoji emoji-26c8"'
            ' role="img" title="cloud with lightning and'
            ' rain">:cloud_with_lightning_and_rain:</span>.</p>'
        )
        fragment = lxml.html.fromstring(test_data)
        fix_emojis(fragment, "google")
        actual_output = lxml.html.tostring(fragment, encoding="unicode")
        expected_output = (
            '<p>See <img alt=":cloud_with_lightning_and_rain:"'
            ' src="http://testserver/static/generated/emoji/images-google-64/26c8.png"'
            ' title="cloud with lightning and rain" style="height: 20px;">.</p>'
        )
        self.assertEqual(actual_output, expected_output)

    def test_latex_math_formulas_in_email(self) -> None:
        msg_id = self.send_stream_message(
            self.example_user("iago"), "Denmark", "Equation: $$d^* = +\\infty$$ is correct."
        )
        verify_body_include = ["Equation: <span>$$d^* = +\\infty$$</span> is correct"]
        email_subject = "#Denmark > test"
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            verify_html_body=True,
            trigger=NotificationTriggers.STREAM_EMAIL,
        )

    def test_empty_backticks_in_missed_message(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "```\n```",
        )
        verify_body_include = ["view it in Zulip Dev Zulip"]
        email_subject = "DMs with Othello, the Moor of Venice"
        self._test_cases(msg_id, verify_body_include, email_subject, verify_html_body=True)

    @override_settings(MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION=2)
    def test_long_term_idle_user_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        zulip_realm = get_realm("zulip")

        # user groups having upto 'MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION'
        # members are small user groups.
        small_user_group = check_add_user_group(
            zulip_realm, "small_user_group", [hamlet, othello], acting_user=None
        )

        large_user_group = check_add_user_group(
            zulip_realm, "large_user_group", [hamlet], acting_user=None
        )
        subgroup = check_add_user_group(
            zulip_realm, "subgroup", [othello, cordelia], acting_user=None
        )
        add_subgroups_to_user_group(large_user_group, [subgroup], acting_user=None)

        def reset_hamlet_as_soft_deactivated_user() -> None:
            nonlocal hamlet
            hamlet = self.example_user("hamlet")
            self.soft_deactivate_user(hamlet)

        # Do note that the event dicts for the missed messages are constructed by hand
        # The part of testing the consumption of missed messages by the worker is left to
        # test_queue_worker.test_missed_message_worker

        # Personal mention in a stream message should soft reactivate the user
        def send_personal_mention() -> None:
            mention = f"@**{hamlet.full_name}**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                {
                    stream_mentioned_message_id: MissedMessageData(
                        trigger=NotificationTriggers.MENTION
                    )
                },
            )

        reset_hamlet_as_soft_deactivated_user()
        self.expect_soft_reactivation(hamlet, send_personal_mention)

        # Direct message should soft reactivate the user
        def send_direct_message() -> None:
            # Soft reactivate the user by sending a personal message
            personal_message_id = self.send_personal_message(othello, hamlet, "Message")
            handle_missedmessage_emails(
                hamlet.id,
                {
                    personal_message_id: MissedMessageData(
                        trigger=NotificationTriggers.DIRECT_MESSAGE
                    )
                },
            )

        reset_hamlet_as_soft_deactivated_user()
        self.expect_soft_reactivation(hamlet, send_direct_message)

        # Hamlet FOLLOWS the topic.
        # 'wildcard_mentions_notify' is disabled to verify the corner case when only
        # 'enable_followed_topic_wildcard_mentions_notify' is enabled (True by default).
        do_set_user_topic_visibility_policy(
            hamlet,
            get_stream("Denmark", hamlet.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        do_change_user_setting(hamlet, "wildcard_mentions_notify", False, acting_user=None)

        # Topic wildcard mention in followed topic should soft reactivate the user
        # hamlet should be a topic participant
        self.send_stream_message(hamlet, "Denmark", "test message")

        def send_topic_wildcard_mention() -> None:
            mention = "@**topic**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                {
                    stream_mentioned_message_id: MissedMessageData(
                        trigger=NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
                    ),
                },
            )

        reset_hamlet_as_soft_deactivated_user()
        self.expect_soft_reactivation(hamlet, send_topic_wildcard_mention)

        # Stream wildcard mention in followed topic should NOT soft reactivate the user
        def send_stream_wildcard_mention() -> None:
            mention = "@**all**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                {
                    stream_mentioned_message_id: MissedMessageData(
                        trigger=NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
                    ),
                },
            )

        reset_hamlet_as_soft_deactivated_user()
        self.expect_to_stay_long_term_idle(hamlet, send_stream_wildcard_mention)

        # Reset
        do_set_user_topic_visibility_policy(
            hamlet,
            get_stream("Denmark", hamlet.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
        )
        do_change_user_setting(hamlet, "wildcard_mentions_notify", True, acting_user=None)

        # Topic Wildcard mention should soft reactivate the user
        reset_hamlet_as_soft_deactivated_user()
        self.expect_soft_reactivation(hamlet, send_topic_wildcard_mention)

        # Stream Wildcard mention should NOT soft reactivate the user
        reset_hamlet_as_soft_deactivated_user()
        self.expect_to_stay_long_term_idle(hamlet, send_stream_wildcard_mention)

        # Small group mention should soft reactivate the user
        def send_small_group_mention() -> None:
            mention = "@*small_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                {
                    stream_mentioned_message_id: MissedMessageData(
                        trigger=NotificationTriggers.MENTION,
                        mentioned_user_group_id=small_user_group.id,
                    ),
                },
            )

        reset_hamlet_as_soft_deactivated_user()
        self.expect_soft_reactivation(hamlet, send_small_group_mention)

        # Large group mention should NOT soft reactivate the user
        def send_large_group_mention() -> None:
            mention = "@*large_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                {
                    stream_mentioned_message_id: MissedMessageData(
                        trigger=NotificationTriggers.MENTION,
                        mentioned_user_group_id=large_user_group.id,
                    ),
                },
            )

        reset_hamlet_as_soft_deactivated_user()
        self.expect_to_stay_long_term_idle(hamlet, send_large_group_mention)

    def test_followed_topic_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        msg_id = self.send_stream_message(othello, "Denmark")

        handle_missedmessage_emails(
            hamlet.id,
            {msg_id: MissedMessageData(trigger=NotificationTriggers.FOLLOWED_TOPIC_EMAIL)},
        )
        self.assert_length(mail.outbox, 1)
        email_subject = mail.outbox[0].subject
        email_body = mail.outbox[0].body
        self.assertEqual("#Denmark > test", email_subject)
        self.assertIn(
            "You are receiving this because you have email notifications enabled for topics you follow.",
            email_body,
        )
