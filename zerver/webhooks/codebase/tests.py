from zerver.lib.test_classes import WebhookTestCase


class CodebaseHookTests(WebhookTestCase):
    TOPIC_NAME = "zulip-terminal"

    def test_codebase_push_message(self) -> None:
        """
        Tests if codebase push event is mapped correctly
        """
        expected_message = "Zulip Contributor pushed to zulip-terminal"
        self.check_webhook("push", self.TOPIC_NAME, expected_message)
