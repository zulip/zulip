from typing import Optional

from django.http import HttpResponse

from zerver.actions.streams import do_deactivate_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, UserProfile


class ReportMessagePayloadTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.hamlet = self.example_user("hamlet")
        self.cordelia = self.example_user("cordelia")
        self.msg_id = self.send_stream_message(self.hamlet, "Denmark", "hello world", "editing")
        self.login("hamlet")
        self.report_message_stream = self.hamlet.realm.get_report_message_stream()
        self.assertTrue(self.report_message_stream is not None)

    def report_message(
        self, user_profile: UserProfile, msg_id: int, reason: str, explanation: Optional[str]
    ) -> HttpResponse:
        info = {
            "reason": reason,
        }
        if explanation is not None:
            info["explanation"] = explanation
        path = "/api/v1/messages/" + str(msg_id) + "/report"
        return self.api_post(user_profile, path, info)

    def detect_hamlet_reported_harassment_message(self) -> Message:
        msg = self.get_last_message()
        self.assertIn("@_**King Hamlet|10** reported a message", msg.content)
        self.assertIn(
            " as containing **`Harassment`** with these notes:\n\n```quote\nfoo bar\n```\n\nOriginal message:\n\n```quote\nhello world\n```",
            msg.content,
        )
        self.report_message_stream = self.hamlet.realm.get_report_message_stream()
        self.assertIsNotNone(self.report_message_stream)
        if self.report_message_stream is not None:
            self.assertEqual(msg.recipient.type_id, self.report_message_stream.id)
        return msg

    def test_deactivate_report_message_stream_error(self) -> None:
        admin_user = self.example_user("iago")
        with self.assertRaisesRegex(Exception, "Cannot deactivate"):
            do_deactivate_stream(self.report_message_stream, acting_user=admin_user)

    def test_message_stream_message(self) -> None:
        resp = self.report_message(self.hamlet, self.msg_id, "harassment", "foo bar")
        self.assert_json_success(resp)
        msg = self.detect_hamlet_reported_harassment_message()
        self.assertIn("to #**Denmark>editing**", msg.content)
        self.assertEqual("sent by King Hamlet", msg.topic_name())

    def test_reporting_private_message(self) -> None:
        # for now, the API allows you to report on a private message where you're not the recipient.
        message_id = self.send_personal_message(self.cordelia, self.hamlet, content="hello world")
        for reason in ["spam", "harassment", "inappropriate", "norms", "other"]:
            resp = self.report_message(self.hamlet, message_id, reason, "foo bar")
            self.assert_json_success(resp)
            if reason == "harassment":
                msg = self.detect_hamlet_reported_harassment_message()
                self.assertIn("to @**King Hamlet|10**", msg.content)

    def test_reporting_huddle_message(self) -> None:
        # for now, the API allows you to report on a private message where you're not in the huddle.
        message_id = self.send_huddle_message(
            from_user=self.cordelia,
            to_users=[self.hamlet, self.example_user("othello")],
            content="hello world",
        )
        resp = self.report_message(self.hamlet, message_id, "harassment", "")
        msg = self.get_last_message()
        self.assert_json_success(resp)
        self.assertIn("sent by @_**Cordelia, Lear's daughter|8**", msg.content)
        self.assertIn("to @**|8** @**|10** @**|12**", msg.content)
        self.assertNotIn("with these notes", msg.content)

    def test_report_message_no_reason_no_explanation(self) -> None:
        for explanation in [None, "", " ", "\n"]:
            resp = self.report_message(self.hamlet, self.msg_id, "other", explanation)
            self.assert_json_error(resp, "For reason=other, an explanation must be provided.")
