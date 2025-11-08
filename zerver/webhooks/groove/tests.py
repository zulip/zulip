from zerver.lib.test_classes import WebhookTestCase


class GrooveHookTests(WebhookTestCase):
    CHANNEL_NAME = "groove"
    URL_TEMPLATE = "/api/v1/external/groove?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "groove"

    # This test simulates the condition when a new ticket comes.
    def test_groove_ticket_started(self) -> None:
        expected_topic_name = "notifications"
        expected_message = """
Test Name submitted new ticket [#9: Test Subject](https://ghostfox.groovehq.com/groove_client/tickets/68659446):

``` quote
The content of the body goes here.
```
""".strip()

        self.check_webhook(
            "ticket_started",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # This simulates the condition when a ticket
    # is assigned to an agent.
    def test_groove_ticket_assigned_agent_only(self) -> None:
        expected_topic_name = "notifications"
        expected_message = "[#9: Test Subject](https://testteam.groovehq.com/groove_client/tickets/68659446) (open) assigned to agent@example.com."
        self.check_webhook(
            "ticket_assigned__agent_only",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # This simulates the condition when a ticket
    # is assigned to an agent in a group.
    def test_groove_ticket_assigned_agent_and_group(self) -> None:
        expected_topic_name = "notifications"
        expected_message = "[#9: Test Subject](https://testteam.groovehq.com/groove_client/tickets/68659446) (open) assigned to agent@example.com from group2."

        self.check_webhook(
            "ticket_assigned__agent_and_group",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # This simulates the condition when a ticket
    # is assigned to a group.
    def test_groove_ticket_assigned_group_only(self) -> None:
        expected_topic_name = "notifications"
        expected_message = "[#9: Test Subject](https://testteam.groovehq.com/groove_client/tickets/68659446) (pending) assigned to group2."
        self.check_webhook(
            "ticket_assigned__group_only",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # This simulates the condition when a ticket
    # is assigned to no one.
    def test_groove_ticket_assigned_no_one(self) -> None:
        self.subscribe(self.test_user, self.CHANNEL_NAME)
        result = self.client_post(
            self.url,
            self.get_body("ticket_assigned__no_one"),
            content_type="application/x-www-form-urlencoded",
            HTTP_X_GROOVE_EVENT="ticket_assigned",
        )
        self.assert_json_success(result)

    # This simulates the notification when an agent replied to a ticket.
    def test_groove_agent_replied(self) -> None:
        expected_topic_name = "notifications"
        expected_message = """
agent@example.com replied to [ticket #776](https://ghostfox.groovehq.com/groove_client/tickets/68667295):

``` quote
Hello , This is a reply from an agent to a ticket
```
""".strip()

        self.check_webhook(
            "agent_replied",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # This simulates the condition when a customer replied to a ticket.
    def test_groove_customer_replied(self) -> None:
        expected_topic_name = "notifications"
        expected_message = """
rambo@example.com replied to [ticket #440](https://ghostfox.groovehq.com/groove_client/tickets/68666538):

``` quote
Hello agent, thanks for getting back. This is how a reply from customer looks like.
```
""".strip()

        self.check_webhook(
            "customer_replied",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    # This simulates the condition when an agent left a note.
    def test_groove_note_added(self) -> None:
        expected_topic_name = "notifications"
        expected_message = """
anotheragent@example.com left a note on [ticket #776](https://ghostfox.groovehq.com/groove_client/tickets/68667295):

``` quote
This is a note added to  a ticket
```
""".strip()

        self.check_webhook(
            "note_added",
            expected_topic_name,
            expected_message,
            content_type="application/x-ww-form-urlencoded",
        )
