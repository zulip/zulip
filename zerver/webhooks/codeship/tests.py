from zerver.lib.test_classes import WebhookTestCase


class CodeshipHookTests(WebhookTestCase):
    CHANNEL_NAME = "codeship"
    URL_TEMPLATE = "/api/v1/external/codeship?stream={stream}&api_key={api_key}"
    TOPIC_NAME = "codeship/docs"
    WEBHOOK_DIR_NAME = "codeship"

    def test_codeship_build_in_testing_status_message(self) -> None:
        """
        Tests if codeship testing status is mapped correctly
        """
        expected_message = "[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch started."
        self.check_webhook("testing_build", self.TOPIC_NAME, expected_message)

    def test_codeship_build_in_error_status_message(self) -> None:
        """
        Tests if codeship error status is mapped correctly
        """
        expected_message = "[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch failed."
        self.check_webhook("error_build", self.TOPIC_NAME, expected_message)

    def test_codeship_build_in_success_status_message(self) -> None:
        """
        Tests if codeship success status is mapped correctly
        """
        expected_message = "[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch succeeded."
        self.check_webhook("success_build", self.TOPIC_NAME, expected_message)

    def test_codeship_build_in_other_status_status_message(self) -> None:
        """
        Tests if codeship other status is mapped correctly
        """
        expected_message = "[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch has some_other_status status."
        self.check_webhook("other_status_build", self.TOPIC_NAME, expected_message)
