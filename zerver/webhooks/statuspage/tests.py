# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class StatuspageHookTests(WebhookTestCase):
    STREAM_NAME = 'statuspage-test'
    URL_TEMPLATE = u"/api/v1/external/statuspage?api_key={api_key}&stream={stream}"

    def test_statuspage_incident(self) -> None:
        expected_subject = u"Database query delays: All Systems Operational"
        expected_message = u"**Database query delays** \n * State: **identified** \n \
* Description: We just encountered that database queries are timing out resulting in inconvenience \
to our end users...we'll do quick fix latest by tommorow !!!"
        self.send_and_test_stream_message('incident_created',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_statuspage_incident_update(self) -> None:
        expected_subject = u"Database query delays: All Systems Operational"
        expected_message = u"**Database query delays** \n * State: **resolved** \n \
* Description: The database issue is resolved."
        self.send_and_test_stream_message('incident_update',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_statuspage_component(self) -> None:
        expected_subject = u"Database component: Service Under Maintenance"
        expected_message = u"**Database component** has changed status \
from **operational** to **under_maintenance**"
        self.send_and_test_stream_message('component_status_update',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("statuspage", fixture_name, file_type="json")
