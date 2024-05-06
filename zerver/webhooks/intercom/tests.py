from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class IntercomWebHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/intercom?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "intercom"

    @patch("zerver.webhooks.intercom.view.check_send_webhook_message")
    def test_ping_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("ping")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_company_created(self) -> None:
        expected_topic_name = "Companies"
        expected_message = """
New company **Kandra Labs** created:
* **User count**: 1
* **Monthly spending**: 0
""".strip()
        self.check_webhook(
            "company_created",
            expected_topic_name,
            expected_message,
        )

    def test_contact_added_email(self) -> None:
        expected_topic_name = "Contact: Azure Bus from St. John's"
        expected_message = "New email jerryguitarist@gmail.com added to contact."
        self.check_webhook(
            "contact_added_email",
            expected_topic_name,
            expected_message,
        )

    def test_contact_created(self) -> None:
        expected_topic_name = "Contact: Azure Bus from St. John's"
        expected_message = """
New contact created:
* **Name (or pseudonym)**: Azure Bus from St. John's
* **Email**: aaron@zulip.com
* **Location**: St. John's, Newfoundland and Labrador, Canada
""".strip()
        self.check_webhook(
            "contact_created",
            expected_topic_name,
            expected_message,
        )

    def test_contact_signed_up(self) -> None:
        expected_topic_name = "User: Lilac Raindrop from St. John's"
        expected_message = """
Contact signed up:
* **Email**: iago@zulip.com
* **Location**: St. John's, Newfoundland and Labrador, Canada
""".strip()
        self.check_webhook(
            "contact_signed_up",
            expected_topic_name,
            expected_message,
        )

    def test_contact_tag_created(self) -> None:
        expected_topic_name = "Contact: Eeshan Garg"
        expected_message = "Contact tagged with the `developer` tag."
        self.check_webhook(
            "contact_tag_created",
            expected_topic_name,
            expected_message,
        )

    def test_contact_tag_deleted(self) -> None:
        expected_topic_name = "Contact: Eeshan Garg"
        expected_message = "The tag `developer` was removed from the contact."
        self.check_webhook(
            "contact_tag_deleted",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_assigned(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = "Tim Abbott assigned to conversation."
        self.check_webhook(
            "conversation_admin_assigned",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_opened(self) -> None:
        expected_topic_name = "Lead: Cordelia, Lear's daughter"
        expected_message = "Eeshan Garg opened the conversation."
        self.check_webhook(
            "conversation_admin_opened",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_closed(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = "Cordelia, Lear's daughter closed the conversation."
        self.check_webhook(
            "conversation_admin_closed",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_snoozed(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = "Cordelia, Lear's daughter snoozed the conversation."
        self.check_webhook(
            "conversation_admin_snoozed",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_unsnoozed(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = "Cordelia, Lear's daughter unsnoozed the conversation."
        self.check_webhook(
            "conversation_admin_unsnoozed",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_replied(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = """
Cordelia, Lear's daughter replied to the conversation:

``` quote
Hey Eeshan! How can I help?
```
""".strip()
        self.check_webhook(
            "conversation_admin_replied",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_noted(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = """
Cordelia, Lear's daughter added a note to the conversation:

``` quote
Talk to Tim about this user's query.
```
""".strip()
        self.check_webhook(
            "conversation_admin_noted",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_admin_single_created(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = """
Cordelia, Lear's daughter initiated a conversation:

``` quote
Hi Eeshan, What's up
```
""".strip()
        self.check_webhook(
            "conversation_admin_single_created",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_user_created(self) -> None:
        expected_topic_name = "Lead: Rose Poodle from St. John's"
        expected_message = """
Rose Poodle from St. John's initiated a conversation:

``` quote
Hello everyone!
```
""".strip()
        self.check_webhook(
            "conversation_user_created",
            expected_topic_name,
            expected_message,
        )

    def test_conversation_user_replied(self) -> None:
        expected_topic_name = "Lead: Eeshan Garg"
        expected_message = """
Eeshan Garg replied to the conversation:

``` quote
Well, I need some help getting access to a developer account.
```
""".strip()
        self.check_webhook(
            "conversation_user_replied",
            expected_topic_name,
            expected_message,
        )

    def test_event_created(self) -> None:
        expected_topic_name = "Events"
        expected_message = "New event **invited-friend** created."
        self.check_webhook(
            "event_created",
            expected_topic_name,
            expected_message,
        )

    def test_user_created(self) -> None:
        expected_topic_name = "User: Aaron Smith"
        expected_message = """
New user created:
* **Name**: Aaron Smith
* **Email**: aaron@zulip.com
""".strip()

        self.check_webhook(
            "user_created",
            expected_topic_name,
            expected_message,
        )

    def test_user_deleted(self) -> None:
        self.check_webhook(
            "user_deleted",
            "User: jerryguitarist@gmail.com",
            "User deleted.",
        )

    def test_user_email_updated(self) -> None:
        self.check_webhook(
            "user_email_updated",
            "Contact: Azure Bus from St. John's",
            "User's email was updated to aaron@zulip.com.",
        )

    def test_user_tag_created(self) -> None:
        self.check_webhook(
            "user_tag_created",
            "User: eeshangarg",
            "The tag `developer` was added to the user.",
        )

    def test_user_tag_deleted(self) -> None:
        expected_topic_name = "User: eeshangarg"
        expected_message = (
            "The tag `CSV Import - 2019-03-26 22:46:04 UTC` was removed from the user."
        )

        self.check_webhook(
            "user_tag_deleted",
            expected_topic_name,
            expected_message,
        )

    def test_user_unsubscribed(self) -> None:
        self.check_webhook(
            "user_unsubscribed",
            "Contact: Eeshan Garg",
            "User unsubscribed from emails.",
        )

    def test_success_on_http_head(self) -> None:
        result = self.client_head(self.url)
        self.assertEqual(result.status_code, 200)
