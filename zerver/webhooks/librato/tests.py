# -*- coding: utf-8 -*-
import urllib

from zerver.lib.test_classes import WebhookTestCase

class LibratoHookTests(WebhookTestCase):
    STREAM_NAME = 'librato'
    URL_TEMPLATE = u"/api/v1/external/librato?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'librato'
    IS_ATTACHMENT = False

    def get_body(self, fixture_name: str) -> str:
        if self.IS_ATTACHMENT:
            return self.webhook_fixture_data("librato", fixture_name, file_type='json')
        return urllib.parse.urlencode({'payload': self.webhook_fixture_data("librato", fixture_name, file_type='json')})

    def test_alert_message_with_default_topic(self) -> None:
        expected_topic = 'Alert alert.name'
        expected_message = "Alert [alert_name](https://metrics.librato.com/alerts#/6294535) has triggered! [Reaction steps](http://www.google.pl)\n>Metric `librato.cpu.percent.idle`, sum was below 44 by 300s, recorded at 2016-03-31 09:11:42 UTC\n>Metric `librato.swap.swap.cached`, average was absent  by 300s, recorded at 2016-03-31 09:11:42 UTC\n>Metric `librato.swap.swap.cached`, derivative was above 9 by 300s, recorded at 2016-03-31 09:11:42 UTC"
        self.send_and_test_stream_message('alert', expected_topic, expected_message, content_type="application/x-www-form-urlencoded")

    def test_alert_message_with_custom_topic(self) -> None:
        custom_topic = 'custom_name'
        self.url = self.build_webhook_url(topic=custom_topic)
        expected_message = "Alert [alert_name](https://metrics.librato.com/alerts#/6294535) has triggered! [Reaction steps](http://www.google.pl)\n>Metric `librato.cpu.percent.idle`, sum was below 44 by 300s, recorded at 2016-03-31 09:11:42 UTC\n>Metric `librato.swap.swap.cached`, average was absent  by 300s, recorded at 2016-03-31 09:11:42 UTC\n>Metric `librato.swap.swap.cached`, derivative was above 9 by 300s, recorded at 2016-03-31 09:11:42 UTC"
        self.send_and_test_stream_message('alert', custom_topic, expected_message, content_type="application/x-www-form-urlencoded")

    def test_three_conditions_alert_message(self) -> None:
        expected_message = "Alert [alert_name](https://metrics.librato.com/alerts#/6294535) has triggered! [Reaction steps](http://www.use.water.pl)\n>Metric `collectd.interface.eth0.if_octets.tx`, absolute_value was above 4 by 300s, recorded at 2016-04-11 20:40:14 UTC\n>Metric `collectd.load.load.longterm`, max was above 99, recorded at 2016-04-11 20:40:14 UTC\n>Metric `librato.swap.swap.cached`, average was absent  by 60s, recorded at 2016-04-11 20:40:14 UTC"
        expected_topic = 'Alert ToHighTemeprature'
        self.send_and_test_stream_message('three_conditions_alert', expected_topic, expected_message, content_type="application/x-www-form-urlencoded")

    def test_alert_clear(self) -> None:
        expected_topic = 'Alert Alert_name'
        expected_message = "Alert [alert_name](https://metrics.librato.com/alerts#/6309313) has cleared at 2016-04-12 13:11:44 UTC!"
        self.send_and_test_stream_message('alert_cleared', expected_topic, expected_message, content_type="application/x-www-form-urlencoded")

    def test_snapshot(self) -> None:
        self.IS_ATTACHMENT = True
        expected_topic = 'Snapshots'
        expected_message = "**Hamlet** sent a [snapshot](http://snapshots.librato.com/chart/nr5l3n0c-82162.png) of [metric](https://metrics.librato.com/s/spaces/167315/explore/1731491?duration=72039&end_time=1460569409)"
        self.send_and_test_stream_message('snapshot', expected_topic, expected_message, content_type="application/x-www-form-urlencoded")
        self.IS_ATTACHMENT = False
