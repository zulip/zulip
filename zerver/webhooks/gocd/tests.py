from zerver.lib.test_classes import WebhookTestCase


class GocdHookTests(WebhookTestCase):
    STREAM_NAME = 'gocd'
    URL_TEMPLATE = "/api/v1/external/gocd?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'gocd'
    TOPIC = 'https://github.com/gocd/gocd'

    def test_gocd_message(self) -> None:
        expected_message = ("Author: Balaji B <balaji@example.com>\n"
                            "Build status: Passed :thumbs_up:\n"
                            "Details: [build log](https://ci.example.com"
                            "/go/tab/pipeline/history/pipelineName)\n"
                            "Comment: my hola mundo changes")

        self.check_webhook(
            "pipeline",
            self.TOPIC,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_failed_message(self) -> None:
        expected_message = ("Author: User Name <username123@example.com>\n"
                            "Build status: Failed :thumbs_down:\n"
                            "Details: [build log](https://ci.example.com"
                            "/go/tab/pipeline/history/pipelineName)\n"
                            "Comment: my hola mundo changes")

        self.check_webhook(
            "pipeline_failed",
            self.TOPIC,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
