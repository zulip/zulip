# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class ZabbixHookTests(WebhookTestCase):
    STREAM_NAME = 'zabbix'
    URL_TEMPLATE = u"/api/v1/external/zabbix?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'zabbix'

    def test_zabbix_alert_message(self) -> None:
        """
        Tests if zabbix alert is handled correctly
        """
        expected_topic = u"www.example.com"
        expected_message = u"PROBLEM (Average) alert on [www.example.com](https://zabbix.example.com/tr_events.php?triggerid=14032&eventid=10528).\nZabbix agent on www.example.com is unreachable for 5 minutes\nAgent ping is Up (1)"
        self.send_and_test_stream_message('zabbix_alert', expected_topic, expected_message)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("zabbix", fixture_name, file_type="json")
