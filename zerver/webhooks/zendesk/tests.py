from zerver.lib.test_classes import WebhookTestCase


class ZenDeskHookTests(WebhookTestCase):
    CHANNEL_NAME = "zendesk"
    URL_TEMPLATE = "/api/v1/external/zendesk?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "zendesk"

    def test_ticket_with_message_in_payload(self) -> None:
        """
        Test Zendesk webhook when the user provides the `message` field and also contains the `ticket_id` and `ticket_title` in the payload
        and no `topic` query param in URL.
        """
        expected_topic = "#7: SAMPLE TICKET: Problems changing address"
        expected_message = "### Ticket #7\n\n**Status:** Open | **Priority:** Normal | **Type:** Incident\n\n**Created by:** Steve Howell on February 3, 2025\n**Assigned to:** Apoorva Pendse\n\n#### Description\n> The customer is facing an issue with updating their address in the system. They need assistance in resolving this as soon as possible.\n\n**Tags:** `change_address`, `help`, `order`\n\n[View Ticket](https://asdf1640.zendesk.com/agent/tickets/7)"

        self.api_channel_message(
            self.test_user,
            "message_with_ticket_id_and_title",
            expected_topic,
            expected_message,
        )

    def test_ticket_with_message_in_payload_with_no_specified_topic(self) -> None:
        """
        Test Zendesk webhook when the user provides the `message` field but doesn't contain the `topic` or
        the `ticket_id` and `ticket_title` pair in the payload
        """
        expected_topic = "zendesk"
        expected_message = "### Ticket #7\n\n**Status:** Open | **Priority:** Normal | **Type:** Problem\n\n**Created by:** Steve Howell on February 3, 2025\n**Assigned to:** Apoorva Pendse\n\n#### Description\n> The customer is facing an issue with updating their address in the system.\n\n**Tags:** `change_address`, `help`, `order`\n\n[View Ticket](https://asdf1640.zendesk.com/agent/tickets/7)"

        self.api_channel_message(
            self.test_user,
            "ticket_user_provided_message",
            expected_topic,
            expected_message,
        )

    def test_ticket_with_message_and_topic_in_payload(self) -> None:
        """
        Test Zendesk webhook when the user provides the `message` and `topic` field in payload.
        """
        expected_topic = "my_zendesk_topic"
        expected_message = "### Ticket #7\n\n**Status:** Open | **Priority:** Normal | **Type:** Incident\n\n**Created by:** Steve Howell on February 3, 2025\n**Assigned to:** Apoorva Pendse\n\n#### Description\n> The customer is facing an issue with updating their address in the system. They need assistance in resolving this as soon as possible.\n\n**Tags:** `change_address`, `help`, `order`\n\n[View Ticket](https://asdf1640.zendesk.com/agent/tickets/7)"

        self.api_channel_message(
            self.test_user,
            "ticket_user_provided_message_and_topic",
            expected_topic,
            expected_message,
        )

    def test_ticket_event_with_no_message(self) -> None:
        """
        Test Zendesk webhook when the user doesn't supply the message field and we default to
        rendering the key-value pairs in the form of a list.
        """
        expected_topic = "#7: Hello world"

        expected_message = "* **ticket_id**: 7\n* **ticket_title**: Hello world\n* **ticket_description**: ----------------------------------------------\n\nApoorva Pendse, Feb 3, 2025, 19:59\n\nI am writing this to create a ticket.\n* **ticket_url**: asdf1640.zendesk.com/agent/tickets/7\n* **ticket_status**: Open\n* **ticket_priority**: Normal\n* **requester_full_name**: testerzulip\n* **assignee_full_name**: Apoorva Pendse\n* **created_at**: February 3, 2025\n* **updated_at**: February 3, 2025\n* **ticket_type**: Incident\n* **tags**: change_address help order\n* **link**: https://asdf1640.zendesk.com/agent/tickets/7"

        self.api_channel_message(
            self.test_user,
            "ticket_create_update",
            expected_topic,
            expected_message,
        )

    def test_long_topic_name(self) -> None:
        """
        Test Zendesk webhook when the user doesn't supply the message field and we default to
        rendering the key-value pairs in the form of a list.
        """
        expected_topic = "#7: SAMPLE TICKET: Problems changing address for the cust..."

        expected_message = "### Ticket #7\n\n**Status:** Open | **Priority:** Normal | **Type:** Incident\n\n**Created by:** Steve Howell on February 3, 2025\n**Assigned to:** Apoorva Pendse\n\n#### Description\n> The customer is facing an issue with updating their address in the system. They need assistance in resolving this as soon as possible.\n\n**Tags:** `change_address`, `help`, `order`\n\n[View Ticket](https://asdf1640.zendesk.com/agent/tickets/7)"

        self.api_channel_message(
            self.test_user,
            "message_with_long_topic_name",
            expected_topic,
            expected_message,
        )
