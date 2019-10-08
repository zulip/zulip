# -*- coding: utf-8 -*-

from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

class FreshdeskHookTests(WebhookTestCase):
    STREAM_NAME = 'freshdesk'
    URL_TEMPLATE = u"/api/v1/external/freshdesk?stream={stream}"

    def test_ticket_creation(self) -> None:
        """
        Messages are generated on ticket creation through Freshdesk's
        "Dispatch'r" service.
        """
        expected_topic = u"#11: Test ticket subject ☃"
        expected_message = u"""Requester ☃ Bob <requester-bob@example.com> created [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

~~~ quote
Test ticket description ☃.
~~~

Type: **Incident**
Priority: **High**
Status: **Pending**"""
        self.api_stream_message(self.TEST_USER_EMAIL, 'ticket_created', expected_topic, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_status_change(self) -> None:
        """
        Messages are generated when a ticket's status changes through
        Freshdesk's "Observer" service.
        """
        expected_topic = u"#11: Test ticket subject ☃"
        expected_message = """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Status: **Resolved** => **Waiting on Customer**"""
        self.api_stream_message(self.TEST_USER_EMAIL, 'status_changed', expected_topic, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_status_change_fixture_without_required_key(self) -> None:
        """
        A fixture without the requisite keys should raise JsonableError.
        """
        self.url = self.build_webhook_url()
        payload = self.get_body('status_changed_fixture_with_missing_key')
        kwargs = {
            'HTTP_AUTHORIZATION': self.encode_credentials(self.TEST_USER_EMAIL),
            'content_type': 'application/x-www-form-urlencoded',
        }
        result = self.client_post(self.url, payload, **kwargs)
        self.assert_json_error(result, 'Missing key triggered_event in JSON')

    def test_priority_change(self) -> None:
        """
        Messages are generated when a ticket's priority changes through
        Freshdesk's "Observer" service.
        """
        expected_topic = u"#11: Test ticket subject"
        expected_message = """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Priority: **High** => **Low**"""
        self.api_stream_message(self.TEST_USER_EMAIL, 'priority_changed', expected_topic, expected_message,
                                content_type="application/x-www-form-urlencoded")

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_unknown_event_payload_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        """
        Ignore unknown event payloads.
        """
        self.url = self.build_webhook_url()
        payload = self.get_body('unknown_payload')
        kwargs = {
            'HTTP_AUTHORIZATION': self.encode_credentials(self.TEST_USER_EMAIL),
            'content_type': 'application/x-www-form-urlencoded',
        }
        result = self.client_post(self.url, payload, **kwargs)
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def note_change(self, fixture: str, note_type: str) -> None:
        """
        Messages are generated when a note gets added to a ticket through
        Freshdesk's "Observer" service.
        """
        expected_topic = u"#11: Test ticket subject"
        expected_message = """Requester Bob <requester-bob@example.com> added a {} note to [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11).""".format(note_type)
        self.api_stream_message(self.TEST_USER_EMAIL, fixture, expected_topic, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_private_note_change(self) -> None:
        self.note_change("private_note", "private")

    def test_public_note_change(self) -> None:
        self.note_change("public_note", "public")

    def test_inline_image(self) -> None:
        """
        Freshdesk sends us descriptions as HTML, so we have to make the
        descriptions Zulip markdown-friendly while still doing our best to
        preserve links and images.
        """
        expected_topic = u"#12: Not enough ☃ guinea pigs"
        expected_message = u"Requester \u2603 Bob <requester-bob@example.com> created [ticket #12](http://test1234zzz.freshdesk.com/helpdesk/tickets/12):\n\n~~~ quote\nThere are too many cat pictures on the internet \u2603. We need more guinea pigs. Exhibit 1:\n\n  \n\n\n[guinea_pig.png](http://cdn.freshdesk.com/data/helpdesk/attachments/production/12744808/original/guinea_pig.png)\n~~~\n\nType: **Problem**\nPriority: **Urgent**\nStatus: **Open**"
        self.api_stream_message(self.TEST_USER_EMAIL, "inline_images", expected_topic, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("freshdesk", fixture_name, file_type="json")
