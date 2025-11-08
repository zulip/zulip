from zerver.lib.test_classes import WebhookTestCase


class FlockHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/flock?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "flock"

    def test_flock_message(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "This is the welcome message!"
        self.check_webhook(
            "messages", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_reply(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "It's interesting how high productivity will go..."
        self.check_webhook(
            "reply", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_note(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "Shared a note"
        self.check_webhook(
            "note", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_reply_note(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "This is reply to Note."
        self.check_webhook(
            "reply_note", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_reply_pinned(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "This is reply to pinned message."
        self.check_webhook(
            "reply_pinned", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_reply_reminder(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "This is a reply to Reminder."
        self.check_webhook(
            "reply_reminder", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_reply_todo(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "This is a reply to Todo notification."
        self.check_webhook(
            "reply_todo", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_pinned(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "Rishabh rawat pinned an item to the conversation"
        self.check_webhook(
            "pinned", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_reminder(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "Rishabh rawat wanted me to remind All"
        self.check_webhook(
            "reminder", expected_topic_name, expected_message, content_type="application/json"
        )

    def test_flock_todo(self) -> None:
        expected_topic_name = "Flock notifications"
        expected_message = "Rishabh rawat added a to-do in New List 1 list"
        self.check_webhook(
            "todo", expected_topic_name, expected_message, content_type="application/json"
        )
