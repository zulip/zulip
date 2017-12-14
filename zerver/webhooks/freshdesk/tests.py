# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class FreshdeskHookTests(WebhookTestCase):
    STREAM_NAME = 'freshdesk'
    URL_TEMPLATE = u"/api/v1/external/freshdesk?stream={stream}"

    def test_ticket_creation(self) -> None:
        """
        Messages are generated on ticket creation through Freshdesk's
        "Dispatch'r" service.
        """
        expected_subject = u"#11: Test ticket subject ☃"
        expected_message = u"""Requester ☃ Bob <requester-bob@example.com> created [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

~~~ quote
Test ticket description ☃.
~~~

Type: **Incident**
Priority: **High**
Status: **Pending**"""
        self.api_stream_message(self.TEST_USER_EMAIL, 'ticket_created', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_status_change(self) -> None:
        """
        Messages are generated when a ticket's status changes through
        Freshdesk's "Observer" service.
        """
        expected_subject = u"#11: Test ticket subject ☃"
        expected_message = """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Status: **Resolved** => **Waiting on Customer**"""
        self.api_stream_message(self.TEST_USER_EMAIL, 'status_changed', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def test_priority_change(self) -> None:
        """
        Messages are generated when a ticket's priority changes through
        Freshdesk's "Observer" service.
        """
        expected_subject = u"#11: Test ticket subject"
        expected_message = """Requester Bob <requester-bob@example.com> updated [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11):

Priority: **High** => **Low**"""
        self.api_stream_message(self.TEST_USER_EMAIL, 'priority_changed', expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def note_change(self, fixture: Text, note_type: Text) -> None:
        """
        Messages are generated when a note gets added to a ticket through
        Freshdesk's "Observer" service.
        """
        expected_subject = u"#11: Test ticket subject"
        expected_message = """Requester Bob <requester-bob@example.com> added a {} note to [ticket #11](http://test1234zzz.freshdesk.com/helpdesk/tickets/11).""".format(note_type)
        self.api_stream_message(self.TEST_USER_EMAIL, fixture, expected_subject, expected_message,
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
        expected_subject = u"#12: Not enough ☃ guinea pigs"
        expected_message = u"Requester \u2603 Bob <requester-bob@example.com> created [ticket #12](http://test1234zzz.freshdesk.com/helpdesk/tickets/12):\n\n~~~ quote\nThere are too many cat pictures on the internet \u2603. We need more guinea pigs. Exhibit 1:\n\n  \n\n\n[guinea_pig.png](http://cdn.freshdesk.com/data/helpdesk/attachments/production/12744808/original/guinea_pig.png)\n~~~\n\nType: **Problem**\nPriority: **Urgent**\nStatus: **Open**"
        self.api_stream_message(self.TEST_USER_EMAIL, "inline_images", expected_subject, expected_message,
                                content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("freshdesk", fixture_name, file_type="json")
