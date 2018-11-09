# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

class DelightedHookTests(WebhookTestCase):
    STREAM_NAME = 'delighted'
    URL_TEMPLATE = "/api/v1/external/delighted?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'delighted'

    def test_feedback_message_promoter(self) -> None:
        expected_topic = "Survey Response"
        expected_message = ("Kudos! You have a new promoter.\n"
                            ">Score of 9/10 from charlie_gravis@example.com"
                            "\n>Your service is fast and flawless!")

        self.send_and_test_stream_message('survey_response_updated_promoter',
                                          expected_topic,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_feedback_message_non_promoter(self) -> None:
        expected_topic = "Survey Response"
        expected_message = ("Great! You have new feedback.\n"
                            ">Score of 5/10 from paul_gravis@example.com"
                            "\n>Your service is slow, but nearly flawless! "
                            "Keep up the good work!")

        self.send_and_test_stream_message('survey_response_updated_non_promoter',
                                          expected_topic,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("delighted", fixture_name, file_type="json")
