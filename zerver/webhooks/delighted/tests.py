from zerver.lib.test_classes import WebhookTestCase


class DelightedHookTests(WebhookTestCase):
    CHANNEL_NAME = "delighted"
    URL_TEMPLATE = "/api/v1/external/delighted?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "delighted"

    def test_feedback_message_promoter(self) -> None:
        expected_topic_name = "Survey response"
        expected_message = """
Kudos! You have a new promoter. Score of 9/10 from charlie_gravis@example.com:

``` quote
Your service is fast and flawless!
```
""".strip()

        self.check_webhook(
            "survey_response_updated_promoter",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_feedback_message_non_promoter(self) -> None:
        expected_topic_name = "Survey response"
        expected_message = (
            "Great! You have new feedback.\n"
            ">Score of 5/10 from paul_gravis@example.com"
            "\n>Your service is slow, but nearly flawless! "
            "Keep up the good work!"
        )
        expected_message = """
Great! You have new feedback. Score of 5/10 from paul_gravis@example.com:

``` quote
Your service is slow, but nearly flawless! Keep up the good work!
```
""".strip()

        self.check_webhook(
            "survey_response_updated_non_promoter",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
