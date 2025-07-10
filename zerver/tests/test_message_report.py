from django.conf import settings
from typing_extensions import Any, override

from zerver.actions.realm_settings import do_set_realm_moderation_request_channel
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.lib.message_report import MAX_REPORT_MESSAGE_SNIPPET_LENGTH
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.lib.topic_link_util import (
    get_message_link_syntax,
    will_produce_broken_stream_topic_link,
)
from zerver.models import UserProfile
from zerver.models.messages import Message
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.users import get_system_bot


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
        self.reported_message_id = self.send_stream_message(
            self.reported_user,
            "Denmark",
            topic_name="civillized discussions",
            content="I squeeze toothpaste from the middle",
        )
        self.reported_message = self.get_last_message()
        assert self.reported_message.id == self.reported_message_id

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

    def get_submitted_moderation_requests(self) -> list[dict[str, Any]]:
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, self.realm.id)

        return (
            Message.objects.filter(
                realm_id=self.realm.id,
                sender_id=notification_bot.id,
                recipient=self.moderation_request_channel.recipient,
            )
            .order_by("-id")
            .values(*["id", "content", DB_TOPIC_NAME])
        )

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

    def test_channel_message_report(self) -> None:
        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "this is crime against food"

        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)
        channel = self.reported_message.recipient.label()
        topic_name = self.reported_message.topic_name()
        message_sent_to = f"{reporting_user_mention} reported #**{channel}>{topic_name}@{self.reported_message_id}** sent by {reported_user_mention}."
        expected_message = """
{message_sent_to}
- Reason: **{report_type}**
- Notes:
```quote
{description}
```
{fence} spoiler **Message sent by {reported_user}**
{reported_message}
{fence}
""".format(
            report_type=report_type,
            description=description,
            reported_user=reported_user_mention,
            message_sent_to=message_sent_to,
            reported_message=self.reported_message.content,
            fence=get_unused_fence(self.reported_message.content),
        )

        result = self.report_message(
            reporting_user, self.reported_message_id, report_type, description
        )
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert len(reports) == 1
        self.assertEqual(reports[0]["content"], expected_message.strip())
        expected_report_topic = f"{self.reported_user.full_name}'s moderation requests"
        self.assertEqual(reports[0][DB_TOPIC_NAME], expected_report_topic)

        # User can report messages in public channels they're not subscribed
        # to.
        self.unsubscribe(reporting_user, "Denmark")
        result = self.report_message(
            reporting_user, self.reported_message_id, report_type, description
        )
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert len(reports) == 2
        self.assertEqual(reports[0]["content"], expected_message.strip())
        expected_report_topic = f"{self.reported_user.full_name}'s moderation requests"
        self.assertEqual(reports[0][DB_TOPIC_NAME], expected_report_topic)

        # User can't report a message in channels they're not a part of.
        private_channel = self.make_stream("private channel", self.realm, invite_only=True)
        self.subscribe(self.reported_user, private_channel.name, True)
        self.reported_message_id = self.send_stream_message(
            self.reported_user,
            private_channel.name,
            topic_name="private discussions",
            content="foo bar",
        )
        private_message = self.get_last_message()
        result = self.report_message(reporting_user, private_message.id, report_type, description)
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
        assert len(reports) == 1
        self.assertIn(expected_message_link_syntax, reports[0]["content"])

    def test_dm_report(self) -> None:
        # Send a DM to be reported
        reported_dm_id = self.send_personal_message(
            self.reported_user,
            self.hamlet,
            content="I dip fries in ice cream",
        )
        reported_dm = self.get_last_message()
        assert reported_dm.id == reported_dm_id

        reporting_user = self.example_user("hamlet")
        report_type = "harassment"
        description = "this is crime against food"
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)

        message_sent_to = f"{reporting_user_mention} reported a DM sent by {reported_user_mention}."
        expected_message = """
{message_sent_to}
- Reason: **{report_type}**
- Notes:
```quote
{description}
```
{fence} spoiler **Message sent by {reported_user}**
{reported_message}
{fence}
""".format(
            report_type=report_type,
            description=description,
            reported_user=reported_user_mention,
            message_sent_to=message_sent_to,
            reported_message=reported_dm.content,
            fence=get_unused_fence(reported_dm.content),
        )

        result = self.report_message(reporting_user, reported_dm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert len(reports) == 1
        self.assertEqual(reports[0]["content"], expected_message.strip())

        # User can't report DM they're not a part of.
        ZOE = self.example_user("ZOE")
        result = self.report_message(ZOE, reported_dm_id, report_type, description)
        self.assert_json_error(result, msg="Invalid message(s)")

    def test_personal_message_report_using_direct_message_group(self) -> None:
        direct_message_group = get_or_create_direct_message_group(
            id_list=[self.hamlet.id, self.reported_user.id],
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
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)

        message_sent_to = f"{reporting_user_mention} reported a DM sent by {reported_user_mention}."
        expected_message = """
{message_sent_to}
- Reason: **{report_type}**
- Notes:
```quote
{description}
```
{fence} spoiler **Message sent by {reported_user}**
{reported_message}
{fence}
""".format(
            report_type=report_type,
            description=description,
            reported_user=reported_user_mention,
            message_sent_to=message_sent_to,
            reported_message=reported_dm.content,
            fence=get_unused_fence(reported_dm.content),
        )

        result = self.report_message(reporting_user, reported_dm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert len(reports) == 1
        self.assertEqual(reports[0]["content"], expected_message.strip())

        # User can't report DM they're not a part of.
        ZOE = self.example_user("ZOE")
        result = self.report_message(ZOE, reported_dm_id, report_type, description)
        self.assert_json_error(result, msg="Invalid message(s)")

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
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)
        iago_user_mention = silent_mention_syntax_for_user(self.example_user("iago"))
        gdm_user_mention = (
            f"{reporting_user_mention}, {iago_user_mention}, and {reported_user_mention}"
        )

        message_sent_to = f"{reporting_user_mention} reported a DM sent by {reported_user_mention} to {gdm_user_mention}."
        expected_message = """
{message_sent_to}
- Reason: **{report_type}**
- Notes:
```quote
{description}
```
{fence} spoiler **Message sent by {reported_user}**
{reported_message}
{fence}
""".format(
            report_type=report_type,
            description=description,
            reported_user=reported_user_mention,
            message_sent_to=message_sent_to,
            reported_message=reported_gdm.content,
            fence=get_unused_fence(reported_gdm.content),
        )

        result = self.report_message(reporting_user, reported_gdm_id, report_type, description)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        assert len(reports) == 1
        self.assertEqual(reports[0]["content"], expected_message.strip())

        # User can't report group direct messages they're not a part of.
        ZOE = self.example_user("ZOE")
        result = self.report_message(ZOE, reported_gdm_id, report_type, description)
        self.assert_json_error(result, msg="Invalid message(s)")

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
        assert len(reports) == 1
        self.assertNotIn(large_message, reports[0]["content"])

        expected_truncated_message = truncate_content(
            large_message, MAX_REPORT_MESSAGE_SNIPPET_LENGTH, "\n[message truncated]"
        )
        self.assertIn(expected_truncated_message, reports[0]["content"])

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
