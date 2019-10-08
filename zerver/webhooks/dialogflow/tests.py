# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class DialogflowHookTests(WebhookTestCase):
    URL_TEMPLATE = u"/api/v1/external/dialogflow?api_key={api_key}&email=AARON@zulip.com"

    def test_dialogflow_default(self) -> None:
        self.url = self.build_webhook_url(
            email="AARON@zulip.com",
            username="aaron",
            user_ip="127.0.0.1"
        )
        expected_message = u"Today the weather in Delhi: Sunny, And the tempreture is 65F"
        self.send_and_test_private_message('default',
                                           expected_message,
                                           content_type="application/json")

    def test_dialogflow_weather_app(self) -> None:
        self.url = self.build_webhook_url(
            email="AARON@zulip.com",
            username="aaron",
            user_ip="127.0.0.1"
        )
        expected_message = u"The weather sure looks great !"
        self.send_and_test_private_message('weather_app',
                                           expected_message,
                                           content_type="application/json")

    def test_dialogflow_alternate_result(self) -> None:
        self.url = self.build_webhook_url(
            email="AARON@zulip.com",
            username="aaron",
            user_ip="127.0.0.1"
        )
        expected_message = u"Weather in New Delhi is nice!"
        self.send_and_test_private_message('alternate_result',
                                           expected_message,
                                           content_type="application/json")

    def test_dialogflow_error_status(self) -> None:
        self.url = self.build_webhook_url(
            email="AARON@zulip.com",
            username="aaron",
            user_ip="127.0.0.1"
        )
        expected_message = u"403 - Access Denied"
        self.send_and_test_private_message('error_status',
                                           expected_message,
                                           content_type="application/json")

    def test_dialogflow_exception(self) -> None:
        self.url = self.build_webhook_url(
            email="AARON@zulip.com",
            username="aaron",
            user_ip="127.0.0.1"
        )
        expected_message = u"DialogFlow couldn't process your query."
        self.send_and_test_private_message('exception',
                                           expected_message,
                                           content_type="application/json")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("dialogflow",
                                         fixture_name,
                                         file_type="json")
