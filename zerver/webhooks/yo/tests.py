from typing import Dict

from zerver.lib.test_classes import WebhookTestCase


class YoHookTests(WebhookTestCase):
    STREAM_NAME = 'yo'
    URL_TEMPLATE = "/api/v1/external/yo?api_key={api_key}"
    FIXTURE_DIR_NAME = 'yo'

    def test_yo_message(self) -> None:
        """
        Yo App sends notification whenever user receives a new Yo from another user.
        """
        cordelia = self.example_user('cordelia')
        self.url = self.build_webhook_url(
            email=cordelia.email,
            username="IAGO",
            user_ip="127.0.0.1",
        )
        expected_message = "Yo from IAGO"
        self.send_and_test_private_message('', expected_message=expected_message,
                                           content_type="application/x-www-form-urlencoded")

    def get_payload(self, fixture_name: str) -> Dict[str, str]:
        return {}
