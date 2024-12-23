from typing_extensions import Any, override

from zerver.actions.realm_settings import do_set_realm_moderation_request_channel
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

        self.offenders_message_id = self.send_stream_message(
            self.example_user("othello"),
            "Denmark",
            topic_name="civillized discussion",
            content="I like pineapple on pizza :)",
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

        result = self.report_message(reporting_user, self.offenders_message_id, "spam")

        self.assert_json_success(result)

    def test_guest_reports_message(self) -> None:
        guest_user = self.example_user("polonius")
        assert guest_user.role == UserProfile.ROLE_GUEST

        result = self.report_message(guest_user, self.offenders_message_id, "spam")

        self.assert_json_error(result, "You can't report this message.")

    def test_user_self_report(self) -> None:
        offender = self.example_user("othello")

        result = self.report_message(
            offender, self.offenders_message_id, "other", "I've made a mistake"
        )

        self.assert_json_error(result, "You can't report this message.")

    def test_other_reason_with_no_explanation(self) -> None:
        result = self.report_message(self.hamlet, self.offenders_message_id, reason="other")

        self.assert_json_error(result, "For reason=other, an explanation must be provided.")

        result = self.report_message(
            self.hamlet,
            self.offenders_message_id,
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
            self.offenders_message_id,
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
