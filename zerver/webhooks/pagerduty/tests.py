# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class PagerDutyHookTests(WebhookTestCase):
    STREAM_NAME = 'pagerduty'
    URL_TEMPLATE = u"/api/v1/external/pagerduty?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'pagerduty'

    def test_trigger(self) -> None:
        expected_message = ':imp: Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) triggered by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) and assigned to [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>foo'
        self.send_and_test_stream_message('trigger', u"incident 3", expected_message)

    def test_unacknowledge(self) -> None:
        expected_message = ':imp: Incident [3](https://zulip-test.pagerduty.com/incidents/P140S4Y) unacknowledged by [Test service](https://zulip-test.pagerduty.com/services/PIL5CUQ) and assigned to [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>foo'
        self.send_and_test_stream_message('unacknowledge', u"incident 3", expected_message)

    def test_resolved(self) -> None:
        expected_message = ':grinning: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) resolved by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        self.send_and_test_stream_message('resolved', u"incident 1", expected_message)

    def test_auto_resolved(self) -> None:
        expected_message = ':grinning: Incident [2](https://zulip-test.pagerduty.com/incidents/PX7K9J2) resolved\n\n>new'
        self.send_and_test_stream_message('auto_resolved', u"incident 2", expected_message)

    def test_acknowledge(self) -> None:
        expected_message = ':no_good: Incident [1](https://zulip-test.pagerduty.com/incidents/PO1XIJ5) acknowledged by [armooo@](https://zulip-test.pagerduty.com/users/POBCFRJ)\n\n>It is on fire'
        self.send_and_test_stream_message('acknowledge', u"incident 1", expected_message)

    def test_no_subject(self) -> None:
        expected_message = u':grinning: Incident [48219](https://dropbox.pagerduty.com/incidents/PJKGZF9) resolved\n\n>mp_error_block_down_critical\u2119\u01b4'
        self.send_and_test_stream_message('mp_fail', u"incident 48219", expected_message)

    def test_bad_message(self) -> None:
        expected_message = 'Unknown pagerduty message\n```\n{\n  "type":"incident.triggered"\n}\n```'
        self.send_and_test_stream_message('bad_message_type', u"pagerduty", expected_message)

    def test_unknown_message_type(self) -> None:
        expected_message = 'Unknown pagerduty message\n```\n{\n  "type":"foo"\n}\n```'
        self.send_and_test_stream_message('unknown_message_type', u"pagerduty", expected_message)
