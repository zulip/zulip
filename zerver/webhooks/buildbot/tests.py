from zerver.lib.test_classes import WebhookTestCase


class BuildbotHookTests(WebhookTestCase):
    CHANNEL_NAME = "buildbot"
    URL_TEMPLATE = "/api/v1/external/buildbot?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "buildbot"

    def test_build_started(self) -> None:
        expected_topic_name = "buildbot-hello"
        expected_message = (
            "Build [#33](http://exampleurl.com/#builders/1/builds/33) for **runtests** started."
        )
        self.check_webhook("started", expected_topic_name, expected_message)

    def test_build_success(self) -> None:
        expected_topic_name = "buildbot-hello"
        expected_message = "Build [#33](http://exampleurl.com/#builders/1/builds/33) (result: success) for **runtests** finished."
        self.check_webhook("finished_success", expected_topic_name, expected_message)

    def test_build_failure(self) -> None:
        expected_topic_name = "general"  # project key is empty
        expected_message = "Build [#34](http://exampleurl.com/#builders/1/builds/34) (result: failure) for **runtests** finished."
        self.check_webhook("finished_failure", expected_topic_name, expected_message)

    def test_build_cancelled(self) -> None:
        expected_topic_name = "zulip/zulip-zapier"
        expected_message = "Build [#10434](https://ci.example.org/#builders/79/builds/307) (result: cancelled) for **AMD64 Ubuntu 18.04 Python 3** finished."
        self.check_webhook("finished_cancelled", expected_topic_name, expected_message)
