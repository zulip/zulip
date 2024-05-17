from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase

# Tests for the Desk.com webhook integration.
#
# The channel name must be provided in the URL-encoded test fixture data,
# and must match CHANNEL_NAME set here.
#
# Example:
#
# stream=deskdotcom&topic=static%20text%20notification&data=This%20is%20a%20custom%20action.
#


class DeskDotComHookTests(WebhookTestCase):
    CHANNEL_NAME = "deskdotcom"
    URL_TEMPLATE = "/api/v1/external/deskdotcom?stream={stream}"
    WEBHOOK_DIR_NAME = "deskdotcom"

    def test_static_text_message(self) -> None:
        expected_topic_name = "static text notification"
        expected_message = "This is a custom action."

        self.api_channel_message(
            self.test_user,
            "static_text",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_case_updated_message(self) -> None:
        expected_topic_name = "case updated notification"
        expected_message = (
            "Case 2 updated. "
            "Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
            "I have a question</a>"
        )

        self.api_channel_message(
            self.test_user,
            "case_updated",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_unicode_text_italian(self) -> None:
        expected_topic_name = "case updated notification"
        expected_message = (
            "Case 2 updated. "
            "Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
            "Il mio hovercraft è pieno di anguille.</a>"
        )

        self.api_channel_message(
            self.test_user,
            "unicode_text_italian",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_unicode_text_japanese(self) -> None:
        expected_topic_name = "case updated notification"
        expected_message = (
            "Case 2 updated. "
            "Link: <a href='https://deskdotcomtest.desk.com/web/agent/case/2'>"
            "私のホバークラフトは鰻でいっぱいです</a>"
        )

        self.api_channel_message(
            self.test_user,
            "unicode_text_japanese",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    @override
    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("deskdotcom", fixture_name, file_type="txt")
