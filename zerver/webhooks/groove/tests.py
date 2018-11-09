# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class GrooveHookTests(WebhookTestCase):
    STREAM_NAME = 'groove'
    URL_TEMPLATE = '/api/v1/external/groove?stream={stream}&api_key={api_key}'

    # This test simulates the condition when a new ticket comes.
    def test_groove_ticket_started(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"New ticket from Test Name\n"
                            u"```quote\n"
                            u"**[Ticket #9: Test Subject](https://ghostfox.groovehq.com/groove_client/tickets/68659446)**\n"
                            u"The content of the body goes here.\n"
                            u"```")
        self.send_and_test_stream_message('ticket_started', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="ticket_started")

    # This simulates the condition when a ticket
    # is assigned to an agent.
    def test_groove_ticket_assigned_agent_only(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"An open ticket has been assigned to agent@example.com\n"
                            u"```quote\n"
                            u"**[Ticket #9: Test Subject](https://testteam.groovehq.com/groove_client/tickets/68659446)**\n"
                            u"```")
        self.send_and_test_stream_message('ticket_assigned_agent_only', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="ticket_assigned")

    # This simulates the condition when a ticket
    # is assigned to an agent in a group.
    def test_groove_ticket_assigned_agent_and_group(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"An open ticket has been assigned to agent@example.com from group2\n"
                            u"```quote\n"
                            u"**[Ticket #9: Test Subject](https://testteam.groovehq.com/groove_client/tickets/68659446)**\n"
                            u"```")
        self.send_and_test_stream_message('ticket_assigned_agent_and_group', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="ticket_assigned")

    # This simulates the condition when a ticket
    # is assigned to a group.
    def test_groove_ticket_assigned_group_only(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"A pending ticket has been assigned to group2\n"
                            u"```quote\n"
                            u"**[Ticket #9: Test Subject](https://testteam.groovehq.com/groove_client/tickets/68659446)**\n"
                            u"```")
        self.send_and_test_stream_message('ticket_assigned_group_only', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="ticket_assigned")

    # This simulates the condition when a ticket
    # is assigned to no one.
    def test_groove_ticket_assigned_no_one(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        result = self.client_post(self.url, self.get_body('ticket_assigned_no_one'),
                                  content_type="application/x-www-form-urlencoded",
                                  HTTP_X_GROOVE_EVENT='ticket_assigned')
        self.assert_json_success(result)

    # This simulates the notification when an agent replied to a ticket.
    def test_groove_agent_replied(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"agent@example.com has just replied to a ticket\n"
                            u"```quote\n"
                            u"**[Ticket #776](https://ghostfox.groovehq.com/groove_client/tickets/68667295)**\n"
                            u"Hello , This is a reply from an agent to a ticket\n"
                            u"```")
        self.send_and_test_stream_message('agent_replied', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="agent_replied")

    # This simulates the condition when a customer replied to a ticket.
    def test_groove_customer_replied(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"rambo@example.com has just replied to a ticket\n"
                            u"```quote\n"
                            u"**[Ticket #440](https://ghostfox.groovehq.com/groove_client/tickets/68666538)**\n"
                            u"Hello agent, thanks for getting back. This is how a reply from customer looks like.\n"
                            u"```")
        self.send_and_test_stream_message('customer_replied', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="customer_replied")

    # This simulates the condition when an agent left a note.
    def test_groove_note_added(self) -> None:
        expected_topic = u"notifications"
        expected_message = (u"anotheragent@example.com has left a note\n"
                            u"```quote\n"
                            u"**[Ticket #776](https://ghostfox.groovehq.com/groove_client/tickets/68667295)**\n"
                            u"This is a note added to  a ticket\n"
                            u"```")
        self.send_and_test_stream_message('note_added', expected_topic, expected_message,
                                          content_type="application/x-ww-form-urlencoded",
                                          HTTP_X_GROOVE_EVENT="note_added")

    # This is for other events than specified.
    def test_groove_ticket_state_changed(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        result = self.client_post(self.url, self.get_body('ticket_state_changed'),
                                  content_type="application/x-www-form-urlencoded",
                                  HTTP_X_GROOVE_EVENT='ticket_state_changed')
        self.assert_json_success(result)

    def test_groove_malformed_payload(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        result = self.client_post(self.url, self.get_body('malformed_payload'),
                                  content_type="application/x-www-form-urlencoded",
                                  HTTP_X_GROOVE_EVENT='ticket_started')
        self.assert_json_error(result, 'Missing required data')

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("groove", fixture_name, file_type="json")
