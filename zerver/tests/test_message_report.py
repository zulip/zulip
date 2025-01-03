from typing_extensions import Any, override

from zerver.actions.realm_settings import do_set_realm_moderation_request_channel
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile


class ReportMessageTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.hamlet = self.example_user("hamlet")
        self.moderation_request_channel = self.make_stream("reported messages", invite_only=True)
        do_set_realm_moderation_request_channel(
            self.hamlet.realm,
            self.moderation_request_channel,
            self.moderation_request_channel.id,
            acting_user=self.hamlet,
        )
        self.reported_user = self.example_user("othello")
        self.offending_message_content = "I like pineapple pizza :)"
        self.offending_message_id = self.send_stream_message(
            self.reported_user,
            "Denmark",
            topic_name="civillized discussion",
            content=self.offending_message_content,
        )

    def report_message(
        self, user_profile: UserProfile, msg_id: int, reason: str, explanation: str | None = None
    ) -> Any:
        report_info = {"reason": reason}
        if explanation:
            report_info["explanation"] = explanation
        return self.api_post(user_profile, f"/api/v1/messages/{msg_id}/report", report_info)

    def test_report_message(self) -> None:
        reporting_user = self.example_user("hamlet")
        reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
        reported_user_mention = silent_mention_syntax_for_user(self.reported_user)
        reason = "spam"
        explanation = ":( i feel attacked"

        result = self.report_message(reporting_user, self.offending_message_id, reason, explanation)
        self.assert_json_success(result)

        report_message = self.get_last_message()
        expected_message = f"""
{reporting_user_mention} reported: #**Denmark>civillized discussion@{self.offending_message_id}**
``` spoiler Message sent by {reported_user_mention}
{self.offending_message_content}
```
- Reason: {reason}
- Explanation: {explanation}
"""
        self.assertEqual(report_message.content, expected_message.strip())

    def test_other_reason_with_no_explanation(self) -> None:
        result = self.report_message(self.hamlet, self.offending_message_id, reason="other")

        self.assert_json_error(result, "For reason=other, an explanation must be provided.")

        result = self.report_message(
            self.hamlet,
            self.offending_message_id,
            reason="other",
            explanation="This is crime against food.",
        )

        self.assert_json_success(result)

    def test_disabled_moderation_request_feature(self) -> None:
        # Disable moderation request feature
        do_set_realm_moderation_request_channel(
            self.hamlet.realm, None, -1, acting_user=self.hamlet
        )

        result = self.report_message(
            self.hamlet,
            self.offending_message_id,
            reason="harassment",
        )
        self.assert_json_error(
            result, "Moderation request channel must be specified to enable message reporting."
        )

        # Re-enable moderation request feature
        do_set_realm_moderation_request_channel(
            self.hamlet.realm,
            self.moderation_request_channel,
            self.moderation_request_channel.id,
            acting_user=self.hamlet,
        )

    # TODO: test report DM messages
    # TODO: test truncated message snippet
    # TODO; test report group messages
