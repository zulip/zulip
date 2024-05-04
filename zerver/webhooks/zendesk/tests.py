from typing import Dict

from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase


class ZenDeskHookTests(WebhookTestCase):
    CHANNEL_NAME = "zendesk"
    URL_TEMPLATE = "/api/v1/external/zendesk?stream={stream}"

    @override
    def get_payload(self, fixture_name: str) -> Dict[str, str]:
        return {
            "ticket_title": self.TICKET_TITLE,
            "ticket_id": str(self.TICKET_ID),
            "message": self.MESSAGE,
            "stream": self.CHANNEL_NAME,
        }

    def do_test(self, expected_topic: str, expected_message: str) -> None:
        self.api_channel_message(
            self.test_user,
            "",
            expected_topic,
            expected_message,
            content_type=None,
        )

    def test_short_topic(self) -> None:
        self.TICKET_ID = 4
        self.TICKET_TITLE = "Test ticket"
        self.MESSAGE = "some message"
        self.do_test(
            expected_topic="#4: Test ticket",
            expected_message="some message",
        )

    def test_long_subject(self) -> None:
        self.TICKET_ID = 4
        self.TICKET_TITLE = "Test ticket" + "!" * 80
        self.MESSAGE = "some message"
        self.do_test(
            expected_topic="#4: Test ticket" + "!" * 42 + "...",
            expected_message="some message",
        )

    def test_long_content(self) -> None:
        self.TICKET_ID = 5
        self.TICKET_TITLE = "Some ticket"
        self.MESSAGE = "New comment:\n> It is better\n* here"
        self.do_test(
            expected_topic="#5: Some ticket",
            expected_message="New comment:\n> It is better\n* here",
        )
