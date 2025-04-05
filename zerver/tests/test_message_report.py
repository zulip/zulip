from django.conf import settings
from typing_extensions import Any, override

from zerver.actions.realm_settings import do_set_realm_moderation_request_channel
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.lib.message_report import MAX_REPORT_MESSAGE_SNIPPET_LENGTH
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.models import UserProfile
from zerver.models.messages import Message
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
        self, user_profile: UserProfile, msg_id: int, reason: str, explanation: str | None = None
    ) -> Any:
        report_info = {"reason": reason}
        if explanation:
            report_info["explanation"] = explanation
        return self.api_post(user_profile, f"/api/v1/messages/{msg_id}/report", report_info)

    def get_submitted_moderation_requests(self) -> list[dict[str, Any]]:
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, self.realm.id)

        return Message.objects.filter(
            realm_id=self.realm.id,
            sender_id=notification_bot.id,
            recipient=self.moderation_request_channel.recipient,
        ).values(*["id", "content", DB_TOPIC_NAME])

    def test_disabled_moderation_request_feature(self) -> None:
        # Disable moderation request feature
        do_set_realm_moderation_request_channel(
            self.hamlet.realm, None, -1, acting_user=self.hamlet
        )

        result = self.report_message(
            self.hamlet,
            self.reported_message_id,
            reason="harassment",
        )
        self.assert_json_error(
            result, "Moderation request channel must be specified to enable message reporting."
        )

    def test_channel_message_report_format(self) -> None:
        reporting_user = self.example_user("hamlet")
        reason = "harassment"
        explanation = "this is crime against food"
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)
        channel = self.reported_message.recipient.label()
        topic_name = self.reported_message.topic_name()
        message_link = f"#**{channel}>{topic_name}@{self.reported_message_id}**"
        expected_message = f"""
{reporting_user_mention} reported {message_link} sent by {reported_user_mention}.
- Reason: **{reason}**
- Notes:
```quote
{explanation}
```
``` spoiler **Message sent by {reported_user_mention}**
{self.reported_message.content}
```
"""
        result = self.report_message(reporting_user, self.reported_message_id, reason, explanation)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        self.assertEqual(reports[0]["content"], expected_message.strip())
        expected_report_topic = f"{self.reported_user.full_name}'s moderation requests"
        self.assertEqual(reports[0][DB_TOPIC_NAME], expected_report_topic)

    def test_dm_report_format(self) -> None:
        # Send a DM to be reported
        reported_dm_id = self.send_personal_message(
            self.reported_user,
            self.hamlet,
            content="I dip fries in ice cream",
        )
        reported_dm = self.get_last_message()
        assert reported_dm.id == reported_dm_id

        reporting_user = self.example_user("hamlet")
        reason = "harassment"
        explanation = "this is crime against food"
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)

        expected_message = f"""
{reporting_user_mention} reported a DM sent by {reported_user_mention} to {reporting_user_mention}.
- Reason: **{reason}**
- Notes:
```quote
{explanation}
```
``` spoiler **Message sent by {reported_user_mention}**
{reported_dm.content}
```
"""
        result = self.report_message(reporting_user, reported_dm_id, reason, explanation)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        self.assertEqual(reports[0]["content"], expected_message.strip())

    def test_gdm_report_format(self) -> None:
        # Send a group DM to be reported
        reported_gdm_id = self.send_group_direct_message(
            self.reported_user,
            [self.hamlet, self.reported_user, self.example_user("iago")],
            content="I eat cereal with water",
        )
        reported_gdm = self.get_last_message()
        assert reported_gdm.id == reported_gdm_id

        reporting_user = self.example_user("hamlet")
        reason = "harassment"
        explanation = "Call the police please"
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)
        iago_user_mention = silent_mention_syntax_for_user(self.example_user("iago"))
        gdm_user_mention = (
            f"{reporting_user_mention}, {iago_user_mention}, and {reported_user_mention}"
        )

        expected_message = f"""
{reporting_user_mention} reported a DM sent by {reported_user_mention} to {gdm_user_mention}.
- Reason: **{reason}**
- Notes:
```quote
{explanation}
```
``` spoiler **Message sent by {reported_user_mention}**
{reported_gdm.content}
```
"""
        result = self.report_message(reporting_user, reported_gdm_id, reason, explanation)
        self.assert_json_success(result)
        reports = self.get_submitted_moderation_requests()
        self.assertEqual(reports[0]["content"], expected_message.strip())

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
        self.assertNotIn(large_message, reports[0]["content"])

        expected_truncated_message = truncate_content(
            large_message, MAX_REPORT_MESSAGE_SNIPPET_LENGTH, "\n[message truncated]"
        )
        self.assertIn(expected_truncated_message, reports[0]["content"])

    def test_other_reason_with_no_explanation(self) -> None:
        result = self.report_message(self.hamlet, self.reported_message_id, reason="other")

        self.assert_json_error(result, "For reason=other, an explanation must be provided.")

        result = self.report_message(
            self.hamlet,
            self.reported_message_id,
            reason="other",
            explanation="This is crime against food.",
        )

        self.assert_json_success(result)
