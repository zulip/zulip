
from zerver.lib.test_classes import WebhookTestCase

class HomeAssistantHookTests(WebhookTestCase):
    STREAM_NAME = 'homeassistant'
    URL_TEMPLATE = "/api/v1/external/homeassistant?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'homeassistant'

    def test_simplereq(self) -> None:
        expected_topic = "homeassistant"
        expected_message = "The sun will be shining today!"

        self.send_and_test_stream_message('simplereq', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_req_with_title(self) -> None:
        expected_topic = "Weather forecast"
        expected_message = "It will be 30 degrees Celsius out there today!"

        self.send_and_test_stream_message('reqwithtitle', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("homeassistant", fixture_name, file_type="json")
