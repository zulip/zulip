from django.conf import settings

from zerver.lib.test_classes import WebhookTestCase
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot


class HelloWorldHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}&stream={stream}"
    DIRECT_MESSAGE_URL_TEMPLATE = "/api/v1/external/helloworld?&api_key={api_key}"
    WEBHOOK_DIR_NAME = "helloworld"

    # Note: Include a test function per each distinct message condition your integration supports
    def test_hello_message(self) -> None:
        expected_topic_name = "Hello World"
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Marilyn Monroe](https://en.wikipedia.org/wiki/Marilyn_Monroe)**"

        # use fixture named helloworld_hello
        self.check_webhook(
            "hello",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_goodbye_message(self) -> None:
        expected_topic_name = "Hello World"
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        # use fixture named helloworld_goodbye
        self.check_webhook(
            "goodbye",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_pm_to_bot_owner(self) -> None:
        # Note that this is really just a test for check_send_webhook_message
        self.URL_TEMPLATE = self.DIRECT_MESSAGE_URL_TEMPLATE
        self.url = self.build_webhook_url()
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        self.send_and_test_private_message(
            "goodbye",
            expected_message=expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_stream_error_pm_to_bot_owner(self) -> None:
        # Note that this is really just a test for check_send_webhook_message
        self.CHANNEL_NAME = "nonexistent"
        self.url = self.build_webhook_url()
        realm = get_realm("zulip")
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)
        expected_message = "Your bot `webhook-bot@zulip.com` tried to send a message to channel #**nonexistent**, but that channel does not exist. Click [here](#channels/new) to create it."
        self.send_and_test_private_message(
            "goodbye",
            expected_message=expected_message,
            content_type="application/x-www-form-urlencoded",
            sender=notification_bot,
        )

    def test_custom_topic(self) -> None:
        # Note that this is really just a test for check_send_webhook_message
        expected_topic_name = "Custom Topic"
        self.url = self.build_webhook_url(topic=expected_topic_name)
        expected_message = "Hello! I am happy to be here! :smile:\nThe Wikipedia featured article for today is **[Goodbye](https://en.wikipedia.org/wiki/Goodbye)**"

        self.check_webhook(
            "goodbye",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
