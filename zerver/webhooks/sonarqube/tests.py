# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class SonarqubeHookTests(WebhookTestCase):
    STREAM_NAME = 'SonarQube'
    URL_TEMPLATE = '/api/v1/external/sonarqube?&api_key={api_key}&stream={stream}'
    FIXTURE_DIR_NAME = 'sonarqube'
    TOPIC = 'Code quality and security'

    def test_new_metrics(self) -> None:
        expected_message = u"""
In project sonar-test, on branch master, check completed with status **error**.
* Metric 'new reliability rating' computed with result: 1 should be less or equal to 1, status: **ok**.
* Metric 'new security rating' computed with result: 1 should be less or equal to 1, status: **ok**.
""".strip()
        self.send_and_test_stream_message('new_metrics', self.TOPIC, expected_message)

    def test_metrics(self) -> None:
        expected_message = """
In project sonar-test, on branch master, check completed with status **error**.
* Metric 'maintainability rating' computed with result: 1 should be less or equal to 1, status: **ok**.
* Metric 'coverage' computed with result: 0.0 should be greater or equal to 80, status: **error**.
* Metric 'duplicated lines density' computed with result: 89.39828080229226 should be less or equal to 3, status: **error**.
""".strip()
        self.send_and_test_stream_message('metrics', self.TOPIC, expected_message)

    def test_no_branch(self) -> None:
        expected_message = """
In project sonar-test check completed with status **error**.
* Metric 'maintainability rating' computed with result: 1 should be less or equal to 1, status: **ok**.
* Metric 'coverage' computed with result: 0.0 should be greater or equal to 80, status: **error**.
* Metric 'duplicated lines density' computed with result: 89.39828080229226 should be less or equal to 3, status: **error**.
""".strip()
        self.send_and_test_stream_message('no_branch', self.TOPIC, expected_message)

    def test_no_value(self) -> None:
        expected_message = """
In project sonar-test, on branch master, check completed with status **error**.
* Metric 'cognitive complexity' computed with result: 35188 should be less or equal to 7, status: **error**.
* Metric 'projects', status: **no_value**.
""".strip()
        self.send_and_test_stream_message('no_value', self.TOPIC, expected_message)
