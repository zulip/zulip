from zerver.lib.test_classes import WebhookTestCase


class InspingHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/insping?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'insping'

    def test_website_state_available_message(self) -> None:
        expected_topic = "insping"
        expected_message = """
State changed to **Available**:
* **URL**: http://privisus.zulipdev.org:9991
* **Response time**: 223 ms
* **Timestamp**: Fri Dec 29 17:23:46 2017
""".strip()

        self.check_webhook(
            "website_state_available",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_website_state_not_responding_message(self) -> None:
        expected_topic = "insping"
        expected_message = """
State changed to **Not Responding**:
* **URL**: http://privisus.zulipdev.org:9991
* **Response time**: 942 ms
* **Timestamp**: Fri Dec 29 17:13:46 2017
""".strip()

        self.check_webhook(
            "website_state_not_responding",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
