from datetime import timedelta

import time_machine
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now as timezone_now
from django_stubs_ext import QuerySetAny
from typing_extensions import Any, override

from zerver.actions.realm_settings import do_set_realm_moderation_request_channel
from zerver.actions.streams import do_set_stream_property
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.lib.message_report import MAX_REPORT_MESSAGE_SNIPPET_LENGTH
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.topic_link_util import (
    get_message_link_syntax,
    will_produce_broken_stream_topic_link,
)
from zerver.lib.url_encoding import pm_message_url, stream_message_url
from zerver.models import UserProfile
from zerver.models.messages import Message
from zerver.models.realms import Realm, get_realm
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.streams import StreamTopicsPolicyEnum
from zerver.models.users import get_system_bot

# Hardcode a specific value to help test end-to-end.
MOCKED_DATE_SENT = timezone_now() + timedelta(days=1)


class ReportMessageTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.hamlet = self.example_user("hamlet")
        self.realm = self.hamlet.realm
        self.reported_user = self.example_user("othello")

        # Set moderation request channel
        self.moderation_request_channel = self.make_stream(
            "reported messages", self.realm, invite_only=True
        )
        do_set_realm_moderation_request_channel(
            self.hamlet.realm,
            self.moderation_request_channel,
            self.moderation_request_channel.id,
            acting_user=self.hamlet,
        )

        # Send a message to be reported in a public channel
        with time_machine.travel(MOCKED_DATE_SENT, tick=False):
            self.reported_message_id = self.send_stream_message(
                self.reported_user,
                "Denmark",
                topic_name="civillized discussions",
                content="I squeeze toothpaste from the middle",
            )
        self.reported_message = self.get_last_message()
        assert self.reported_message.id == self.reported_message_id

    def check_channel_message_report_details(
        self,
        report_description: str,
        report_type: str,
        reported_message: Message,
        reported_user: UserProfile,
        reporting_user: UserProfile,
        submitted_report: Message | None,
    ) -> None:
        assert submitted_report is not None
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(reported_user)
        reported_message_date_sent = datetime_to_global_time(reported_message.date_sent)

        channel_name = reported_message.recipient.label()
        channel_id = reported_message.recipient.type_id
        topic_name = reported_message.topic_name()
        channel_message_link = get_message_link_syntax(
            channel_id, channel_name, topic_name, reported_message.id
        )

        message_sent_to = f"{reporting_user_mention} reported a message sent by {reported_user_mention} at {reported_message_date_sent}."
        expected_message = """
{message_sent_to}
```quote
**{report_type}**. {description}
```

{fence} spoiler Original message at {channel_message_link}
{reported_message}
{fence}
""".format(
            report_type=Realm.REPORT_MESSAGE_REASONS[report_type],
            description=report_description,
            channel_message_link=channel_message_link,
            message_sent_to=message_sent_to,
            reported_message=reported_message.content,
            fence=get_unused_fence(reported_message.content),
        )

        self.assertEqual(submitted_report.content, expected_message.strip())
        expected_report_topic = f"{reported_user.full_name} moderation"
        self.assertEqual(submitted_report.topic_name(), expected_report_topic)

        # Make sure channel message link is accessible.
        message_link = stream_message_url(
            None,
            dict(
                id=reported_message.id,
                stream_id=channel_id,
                display_recipient=channel_name,
                topic=topic_name,
            ),
            include_base_url=False,
        )

        expected_message_link_html = (
            f'<p>Original message at <a class="message-link" href="/{message_link}">'
        )
        assert submitted_report.rendered_content is not None
        self.assertIn(expected_message_link_html, submitted_report.rendered_content)

    def build_direct_message_report_template(
        self,
        direct_message_link: str,
        message_sent_to: str,
        report_description: str,
        report_type: str,
        reported_dm_content: str,
    ) -> str:
        return """
{message_sent_to}
```quote
**{report_type}**. {description}
```

{fence} spoiler [Original message]({direct_message_link})
{reported_message}
{fence}
""".format(
            report_type=Realm.REPORT_MESSAGE_REASONS[report_type],
            description=report_description,
            direct_message_link=direct_message_link,
            message_sent_to=message_sent_to,
            reported_message=reported_dm_content,
            fence=get_unused_fence(reported_dm_content),
        )

    def check_direct_message_report_details(
        self,
        dm_recipient: UserProfile,
        report_description: str,
        report_type: str,
        reported_dm: Message,
        reported_user: UserProfile,
        reporting_user: UserProfile,
        submitted_report: Message | None,
    ) -> None:
        assert submitted_report is not None
        realm = get_realm("zulip")
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(reported_user)
        reported_dm_date_sent = datetime_to_global_time(reported_dm.date_sent)

        if reported_user != reporting_user:
            message_sent_to = f"{reporting_user_mention} reported a direct message sent by {reported_user_mention} at {reported_dm_date_sent}."
        else:
            dm_recipient_mention = silent_mention_syntax_for_user(dm_recipient)
            message_sent_to = f"{reporting_user_mention} reported a direct message sent by {reported_user_mention} to {dm_recipient_mention} at {reported_dm_date_sent}."

        direct_message_link = pm_message_url(
            realm,
            dict(
                id=reported_dm.id,
                display_recipient=get_display_recipient(reported_dm.recipient),
            ),
        )
        expected_message = self.build_direct_message_report_template(
            direct_message_link=direct_message_link,
            message_sent_to=message_sent_to,
            report_description=report_description,
            report_type=report_type,
            reported_dm_content=reported_dm.content,
        )
        self.assertEqual(submitted_report.content, expected_message.strip())

    def check_group_direct_message_report_details(
        self,
        report_description: str,
        report_type: str,
        reported_gdm: Message,
        reported_user: UserProfile,
        reporting_user: UserProfile,
        submitted_report: Message | None,
    ) -> None:
        assert submitted_report is not None
        realm = get_realm("zulip")
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(reported_user)
        reported_gdm_date_sent = datetime_to_global_time(reported_gdm.date_sent)

        recipient_list = sorted(
            [
                silent_mention_syntax_for_user(user)
                for user in get_display_recipient(reported_gdm.recipient)
                if user["id"] is not reported_user.id
            ]
        )
        last_recipient_user = recipient_list.pop()
        recipient_users: str = ", ".join(recipient_list)
        if len(recipient_list) > 1:
            recipient_users += ","
        message_sent_to = f"{reporting_user_mention} reported a direct message sent by {reported_user_mention} to {recipient_users} and {last_recipient_user} at {reported_gdm_date_sent}."
        direct_message_link = pm_message_url(
            realm,
            dict(
                id=reported_gdm.id,
                display_recipient=get_display_recipient(reported_gdm.recipient),
            ),
        )
        expected_message = self.build_direct_message_report_template(
            direct_message_link=direct_message_link,
            message_sent_to=message_sent_to,
            report_description=report_description,
            report_type=report_type,
            reported_dm_content=reported_gdm.content,
        )
        self.assertEqual(submitted_report.content, expected_message.strip())

    def report_message(
        self,
        user_profile: UserProfile,
        msg_id: int,
        report_type: str,
        description: str | None = None,
    ) -> Any:
        report_info = {"report_type": report_type}
        if description:
            report_info["description"] = description
        return self.api_post(user_profile, f"/api/v1/messages/{msg_id}/report", report_info)

    def get_submitted_moderation_requests(self) -> QuerySetAny[Message]:
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, self.realm.id)

        return Message.objects.filter(
            realm_id=self.realm.id,
            sender_id=notification_bot.id,
            recipient=self.moderation_request_channel.recipient,
        ).order_by("-id")

    def test_disabled_moderation_request_feature(self) -> None:
        # Disable moderation request feature
        do_set_realm_moderation_request_channel(
            self.hamlet.realm, None, -1, acting_user=self.hamlet
        )

        result = self.report_message(
            self.hamlet,
            self.reported_message_id,
            report_type="harassment",
        )
        self.assert_json_error(result, "Message reporting is not enabled in this organization.")

    def test_public_channel_message_report(self) -> None:
        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "this is crime against food"

        result = self.report_message(
            reporting_user, self.reported_message_id, report_type, description
        )
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        self.check_channel_message_report_details(
            report_description=description,
            report_type=report_type,
            reported_message=self.reported_message,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

        # User can report messages in public channels they're not subscribed
        # to.
        self.unsubscribe(reporting_user, "Denmark")
        result = self.report_message(
            reporting_user, self.reported_message_id, report_type, description
        )
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 2
        self.check_channel_message_report_details(
            report_description=description,
            report_type=report_type,
            reported_message=self.reported_message,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

    @time_machine.travel(MOCKED_DATE_SENT, tick=False)
    def test_private_channel_message_report(self) -> None:
        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "this is crime against food"
        private_channel = self.make_stream("private channel", self.realm, invite_only=True)
        self.subscribe(reporting_user, private_channel.name)
        self.subscribe(self.reported_user, private_channel.name)

        reported_private_channel_message_id = self.send_stream_message(
            self.reported_user,
            private_channel.name,
            content="I dip fries in ice cream",
        )
        reported_private_channel_message = self.get_last_message()
        assert reported_private_channel_message.id == reported_private_channel_message_id

        result = self.report_message(
            reporting_user, reported_private_channel_message_id, report_type, description
        )
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        self.check_channel_message_report_details(
            report_description=description,
            report_type=report_type,
            reported_message=reported_private_channel_message,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

        # User can't report a message in channels they're not a part of.
        result = self.report_message(
            self.example_user("ZOE"),
            reported_private_channel_message_id,
            report_type,
            description,
        )
        self.assert_json_error(result, msg="Invalid message(s)")

    def test_reported_channel_message_narrow_link(self) -> None:
        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "this is crime against food"

        # Check object IDs in message link syntax is accurate.
        # This channel name will generate a narrow URL for its link syntax.
        obscure_channel_name = "Sw*den"
        self.assertTrue(will_produce_broken_stream_topic_link(obscure_channel_name))
        obscure_channel = self.make_stream(obscure_channel_name, self.realm)
        self.subscribe(self.reported_user, obscure_channel.name, True)
        message_id = self.send_stream_message(
            self.reported_user,
            obscure_channel.name,
            topic_name="",
            content="foo baz",
        )

        result = self.report_message(
            reporting_user,
            message_id,
            report_type,
            description,
        )
        self.assert_json_success(result)
        expected_message_link_syntax = get_message_link_syntax(
            obscure_channel.id,
            obscure_channel.name,
            "",
            message_id,
        )
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        report = reports.last()
        assert report is not None
        self.assertIn(expected_message_link_syntax, report.content)

    @time_machine.travel(MOCKED_DATE_SENT, tick=False)
    def test_dm_report(self) -> None:
        # Send a DM to be reported
        dm_recipient = self.hamlet
        reported_dm_id = self.send_personal_message(
            self.reported_user,
            dm_recipient,
            content="I dip fries in ice cream",
        )
        reported_dm = self.get_last_message()
        assert reported_dm.id == reported_dm_id
        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "this is crime against food"

        result = self.report_message(reporting_user, reported_dm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        self.check_direct_message_report_details(
            dm_recipient=dm_recipient,
            report_description=description,
            report_type=report_type,
            reported_dm=reported_dm,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

        # User can't report DM they're not a part of.
        ZOE = self.example_user("ZOE")
        result = self.report_message(ZOE, reported_dm_id, report_type, description)
        self.assert_json_error(result, msg="Invalid message(s)")

    @time_machine.travel(MOCKED_DATE_SENT, tick=False)
    def test_dm_to_oneself(self) -> None:
        dm_recipient = self.reported_user
        reported_dm_id = self.send_personal_message(
            self.reported_user,
            dm_recipient,
            content="Hi, me!",
        )
        reported_dm = self.get_last_message()
        assert reported_dm.id == reported_dm_id

        reporting_user = self.reported_user
        report_type = "harassment"
        description = "just testing"

        result = self.report_message(reporting_user, reported_dm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        assert reporting_user == self.reported_user
        self.check_direct_message_report_details(
            dm_recipient=dm_recipient,
            report_description=description,
            report_type=report_type,
            reported_dm=reported_dm,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

    @time_machine.travel(MOCKED_DATE_SENT, tick=False)
    def test_reporting_own_dm_to_other(self) -> None:
        dm_recipient = self.hamlet
        reported_dm_id = self.send_personal_message(
            self.reported_user,
            dm_recipient,
            content="Hi, you!",
        )
        reported_dm = self.get_last_message()
        assert reported_dm.id == reported_dm_id

        reporting_user = self.reported_user
        report_type = "harassment"
        description = "just testing"

        result = self.report_message(reporting_user, reported_dm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        assert reporting_user == self.reported_user
        self.check_direct_message_report_details(
            dm_recipient=dm_recipient,
            report_description=description,
            report_type=report_type,
            reported_dm=reported_dm,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

    @time_machine.travel(MOCKED_DATE_SENT, tick=False)
    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_personal_message_report_using_direct_message_group(self) -> None:
        dm_recipient = self.hamlet
        direct_message_group = get_or_create_direct_message_group(
            id_list=[dm_recipient.id, self.reported_user.id],
        )

        # Send a DM to be reported
        reported_dm_id = self.send_personal_message(
            self.reported_user,
            self.hamlet,
            content="I dip fries in ice cream",
        )
        reported_dm = self.get_last_message()
        assert reported_dm.id == reported_dm_id
        assert reported_dm.recipient == direct_message_group.recipient

        reporting_user = self.hamlet
        report_type = "harassment"
        description = "this is crime against food"
        result = self.report_message(reporting_user, reported_dm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        self.check_direct_message_report_details(
            dm_recipient=dm_recipient,
            report_description=description,
            report_type=report_type,
            reported_dm=reported_dm,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

    def test_gdm_report(self) -> None:
        # Send a group DM to be reported
        reported_gdm_id = self.send_group_direct_message(
            self.reported_user,
            [self.hamlet, self.reported_user, self.example_user("iago")],
            content="I eat cereal with water",
        )
        reported_gdm = self.get_last_message()
        assert reported_gdm.id == reported_gdm_id

        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "Call the police please"
        result = self.report_message(reporting_user, reported_gdm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        self.check_group_direct_message_report_details(
            report_description=description,
            report_type=report_type,
            reported_gdm=reported_gdm,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

        # User can't report group direct messages they're not a part of.
        ZOE = self.example_user("ZOE")
        result = self.report_message(ZOE, reported_gdm_id, report_type, description)
        self.assert_json_error(result, msg="Invalid message(s)")

    @time_machine.travel(MOCKED_DATE_SENT, tick=False)
    def test_gdm_report_with_more_than_3_recipients(self) -> None:
        reported_gdm_id = self.send_group_direct_message(
            self.reported_user,
            [self.hamlet, self.reported_user, self.example_user("ZOE"), self.example_user("iago")],
            content="I eat cereal with water",
        )
        reported_gdm = self.get_last_message()
        assert reported_gdm.id == reported_gdm_id

        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "Call the police please"

        result = self.report_message(reporting_user, reported_gdm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        self.check_group_direct_message_report_details(
            report_description=description,
            report_type=report_type,
            reported_gdm=reported_gdm,
            reported_user=self.reported_user,
            reporting_user=reporting_user,
            submitted_report=reports.last(),
        )

    def test_truncate_reported_message(self) -> None:
        large_message = "." * (MAX_REPORT_MESSAGE_SNIPPET_LENGTH + 1)
        reported_truncate_message_id = self.send_stream_message(
            self.reported_user,
            "Denmark",
            topic_name="civillized discussions",
            content=large_message,
        )
        reported_truncate_message = self.get_last_message()
        assert reported_truncate_message.id == reported_truncate_message_id

        reporting_user = self.example_user("hamlet")

        result = self.report_message(reporting_user, reported_truncate_message_id, "spam")
        self.assert_json_success(result)

        reports = self.get_submitted_moderation_requests()
        assert reports.count() == 1
        report = reports.last()
        assert report is not None
        self.assertNotIn(large_message, report.content)

        expected_truncated_message = truncate_content(
            large_message, MAX_REPORT_MESSAGE_SNIPPET_LENGTH, "\n[message truncated]"
        )
        self.assertIn(expected_truncated_message, report.content)

    def test_other_report_type_with_no_description(self) -> None:
        result = self.report_message(self.hamlet, self.reported_message_id, report_type="other")

        self.assert_json_error(result, "An explanation is required.")

        result = self.report_message(
            self.hamlet,
            self.reported_message_id,
            report_type="other",
            description="This is crime against food.",
        )

        self.assert_json_success(result)

    def test_message_report_to_channel_with_topics_disabled(self) -> None:
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, self.realm.id)
        do_set_stream_property(
            self.moderation_request_channel,
            "topics_policy",
            StreamTopicsPolicyEnum.empty_topic_only.value,
            self.hamlet,
        )

        result = self.report_message(
            self.hamlet,
            self.reported_message_id,
            report_type="harassment",
        )
        self.assert_json_success(result)
        report_msg = self.get_last_message()
        self.assertEqual(report_msg.sender_id, notification_bot.id)
        self.assertEqual(report_msg.topic_name(), "")
        self.assertIn("reported", report_msg.content)
