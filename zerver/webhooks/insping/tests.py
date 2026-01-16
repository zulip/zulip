from zerver.lib.test_classes import WebhookTestCase


class InspingHookTests(WebhookTestCase):
    def test_website_state_available_message(self) -> None:
        expected_topic_name = "insping"
        expected_message = """
State changed to **Available**:
* **URL**: http://privisus.zulipdev.org:9991
* **Response time**: 223 ms
* **Timestamp**: <time:2017-12-29T17:23:46+00:00>
""".strip()

        self.check_webhook(
            "website_state_available",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_website_state_not_responding_message(self) -> None:
        expected_topic_name = "insping"
        expected_message = """
State changed to **Not Responding**:
* **URL**: http://privisus.zulipdev.org:9991
* **Response time**: 942 ms
* **Timestamp**: <time:2017-12-29T17:13:46+00:00>
""".strip()

        self.check_webhook(
            "website_state_not_responding",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
