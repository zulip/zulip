from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class FreshdeskHookTests(WebhookTestCase):
    CHANNEL_NAME = "freshdesk"
    URL_TEMPLATE = "/api/v1/external/freshdesk?stream={stream}"
    WEBHOOK_DIR_NAME = "freshdesk"

    def test_ticket_creation(self) -> None:
        """
        Messages are generated on ticket creation through Freshdesk's
        "Dispatch'r" service.
        """
        expected_topic_name = "#11: Test ticket subject ☃"
        expected_message = """
Requester ☃ Bob <requester-bob@example.com> created [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

``` quote
Test ticket description ☃.
```

* **Type**: Incident
* **Priority**: High
* **Status**: Pending
""".strip()

        self.api_channel_message(
            self.test_user,
            "ticket_created",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_status_change(self) -> None:
        """
        Messages are generated when a ticket's status changes through
        Freshdesk's "Observer" service.
        """
        expected_topic_name = "#11: Test ticket subject ☃"
        expected_message = """
Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

* **Status**: Resolved -> Waiting on Customer
""".strip()

        self.api_channel_message(
            self.test_user,
            "status_changed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_priority_change(self) -> None:
        """
        Messages are generated when a ticket's priority changes through
        Freshdesk's "Observer" service.
        """
        expected_topic_name = "#11: Test ticket subject"
        expected_message = """
Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

* **Priority**: High -> Low
""".strip()
        self.api_channel_message(
            self.test_user,
            "priority_changed",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_unknown_event_payload_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        """
        Ignore unknown event payloads.
        """
        self.url = self.build_webhook_url()
        payload = self.get_body("unknown_payload")
        result = self.client_post(
            self.url,
            payload,
            HTTP_AUTHORIZATION=self.encode_email(self.test_user.email),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def note_change(self, fixture: str, note_type: str) -> None:
        """
        Messages are generated when a note gets added to a ticket through
        Freshdesk's "Observer" service.
        """
        expected_topic_name = "#11: Test ticket subject"
        expected_message = """
Requester Bob <requester-bob@example.com> added a {} note to \
[ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11).
""".strip().format(note_type)
        self.api_channel_message(
            self.test_user,
            fixture,
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_private_note_change(self) -> None:
        self.note_change("private_note", "private")

    def test_public_note_change(self) -> None:
        self.note_change("public_note", "public")

    def test_inline_image(self) -> None:
        """
        Freshdesk sends us descriptions as HTML, so we have to make the
        descriptions Zulip Markdown-friendly while still doing our best to
        preserve links and images.
        """
        expected_topic_name = "#12: Not enough ☃ guinea pigs"
        expected_message = """
Requester \u2603 Bob <requester-bob@example.com> created [ticket #12](http://test1234zzz.freshdesk.com/helpdesk/tickets/12):\n\n``` quote\nThere are too many cat pictures on the internet \u2603. We need more guinea pigs.\nExhibit 1:\n\n  \n\n[guinea_pig.png](http://cdn.freshdesk.com/data/helpdesk/attachments/production/12744808/original/guinea_pig.png)\n```\n\n* **Type**: Problem\n* **Priority**: Urgent\n* **Status**: Open
""".strip()
        self.api_channel_message(
            self.test_user,
            "inline_images",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
