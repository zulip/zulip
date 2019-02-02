# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class GocdHookTests(WebhookTestCase):
    STREAM_NAME = 'gocd'
    URL_TEMPLATE = "/api/v1/external/gocd?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'gocd'
    TOPIC = 'https://github.com/gocd/gocd'

    def test_gocd_message(self) -> None:
        expected_message = (u"Author: Balaji B <balaji@example.com>\n"
                            u"Build status: Passed :thumbs_up:\n"
                            u"Details: [build log](https://ci.example.com"
                            u"/go/tab/pipeline/history/pipelineName)\n"
                            u"Comment: my hola mundo changes")

        self.send_and_test_stream_message(
            'pipeline',
            self.TOPIC,
            expected_message,
            content_type="application/x-www-form-urlencoded"
        )

    def test_failed_message(self) -> None:
        expected_message = (u"Author: User Name <username123@example.com>\n"
                            u"Build status: Failed :thumbs_down:\n"
                            u"Details: [build log](https://ci.example.com"
                            u"/go/tab/pipeline/history/pipelineName)\n"
                            u"Comment: my hola mundo changes")

        self.send_and_test_stream_message(
            'pipeline_failed',
            self.TOPIC,
            expected_message,
            content_type="application/x-www-form-urlencoded"
        )

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("gocd", fixture_name, file_type="json")
