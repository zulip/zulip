# -*- coding: utf-8 -*-
import time as t
from typing import Text
from zerver.lib.test_classes import WebhookTestCase
current_time = float(t.time())
time_delta_in_hours = (float(1517759100) - current_time)/float(3600)

class BeeminderHookTests(WebhookTestCase):
    STREAM_NAME = 'beeminder'
    URL_TEMPLATE = u"/api/v1/external/beeminder?api_key={api_key}&email=AARON@zulip.com"

    def test_beeminder_derail(self) -> None:
        expected_subject = u"beekeeper"
        expected_message = u"Hello **aaron**! I am the Beeminder bot! :octopus: \n You are going to derail \
        from goal **gainweight** in **{:0.1f} hours** \n You need **+2 in 7 days (60)** to avoid derailing \n * Pledge: **0$** :relieved:".format(time_delta_in_hours)
        self.send_and_test_stream_message('derail',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_beeminder_derail_pm(self) -> None:
        self.url = self.build_webhook_url(
            email="AARON@zulip.com",
            username="aaron",
            user_ip="127.0.0.1"
        )
        expected_message = u"I am the Beeminder bot! :octopus: \n You are going to derail from \
        goal **gainweight** in **{:0.1f} hours** \n You need **+2 in 7 days (60)** to avoid derailing \n * Pledge: **5$**:worried:".format(time_delta_in_hours)
        self.send_and_test_private_message('derail_pm',
                                           expected_message,
                                           content_type="application/json")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("beeminder", fixture_name, file_type="json")
