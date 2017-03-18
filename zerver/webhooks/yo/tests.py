# -*- coding: utf-8 -*-
from typing import Any, Dict, Text
from zerver.lib.test_classes import WebhookTestCase

class YoHookTests(WebhookTestCase):
    STREAM_NAME = 'yo'
    URL_TEMPLATE = u"/api/v1/external/yo?email={email}&api_key={api_key}&username={username}&user_ip={ip}"
    FIXTURE_DIR_NAME = 'yo'

    def test_yo_message(self):
        # type: () -> None
        """
        Yo App sends notification whenever user receives a new Yo from another user.
        """
        expected_message = u"Yo from IAGO"
        self.send_and_test_private_message('', expected_message=expected_message,
                                           content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name):
        # type: (Text) -> Dict[str, Any]
        return {}

    def build_webhook_url(self):
        # type: () -> Text
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        email = "cordelia@zulip.com"
        username = "IAGO"
        ip = "127.0.0.1"
        return self.URL_TEMPLATE.format(email=email, api_key=api_key, username=username, ip=ip)
