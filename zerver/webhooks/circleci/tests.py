# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class CircleCiHookTests(WebhookTestCase):
    STREAM_NAME = 'circleci'
    URL_TEMPLATE = u"/api/v1/external/circleci?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'circleci'

    def test_circleci_build_in_success_status(self) -> None:
        expected_topic = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch succeeded."
        self.send_and_test_stream_message('build_passed', expected_topic, expected_message)

    def test_circleci_build_in_failed_status(self) -> None:
        expected_topic = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch failed."
        self.send_and_test_stream_message('build_failed', expected_topic, expected_message)

    def test_circleci_build_in_failed_status_when_previous_build_failed_too(self) -> None:
        expected_topic = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch is still failing."
        self.send_and_test_stream_message('build_failed_when_previous_build_failed', expected_topic, expected_message)

    def test_circleci_build_in_success_status_when_previous_build_failed_too(self) -> None:
        expected_topic = u"RepoName"
        expected_message = u"[Build](https://circleci.com/gh/username/project/build_number) triggered by username on master branch fixed."
        self.send_and_test_stream_message('build_passed_when_previous_build_failed', expected_topic, expected_message)
