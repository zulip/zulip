# -*- coding: utf-8 -*-
from six import text_type
from typing import Dict, Union
from zerver.lib.test_classes import WebhookTestCase

class BitbucketHookTests(WebhookTestCase):
    STREAM_NAME = 'bitbucket'
    URL_TEMPLATE = "/api/v1/external/bitbucket?payload={payload}&stream={stream}"
    FIXTURE_DIR_NAME = 'bitbucket'
    EXPECTED_SUBJECT = u"Repository name"
    EXPECTED_SUBJECT_BRANCH_EVENTS = u"Repository name / master"

    def test_bitbucket_on_push_event(self):
        # type: () -> None
        fixture_name = 'push'
        self.url = self.build_url(fixture_name)
        commit_info = u'* [25f93d2](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12): c'
        expected_message = u"kolaszek pushed to branch master\n\n{}".format(commit_info)
        self.send_and_test_stream_message(fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message, **self.api_auth(self.TEST_USER_EMAIL))

    def test_bitbucket_on_push_commits_above_limit_event(self):
        # type: () -> None
        fixture_name = 'push_commits_above_limit'
        self.url = self.build_url(fixture_name)
        commit_info = u'* [25f93d2](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12): c\n'
        expected_message = u"kolaszek pushed to branch master\n\n{}[and 30 more commit(s)]".format(commit_info * 20)
        self.send_and_test_stream_message(fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message, **self.api_auth(self.TEST_USER_EMAIL))

    def test_bitbucket_on_force_push_event(self):
        # type: () -> None
        fixture_name = 'force_push'
        self.url = self.build_url(fixture_name)
        expected_message = u"kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name)"
        self.send_and_test_stream_message(fixture_name, self.EXPECTED_SUBJECT, expected_message, **self.api_auth(self.TEST_USER_EMAIL))

    def get_body(self, fixture_name):
        # type: (text_type) -> Union[text_type, Dict[str, text_type]]
        return {}

    def get_payload(self, fixture_name):
        # type: (text_type) -> Union[text_type, Dict[str, text_type]]
        return self.fixture_data(self.FIXTURE_DIR_NAME, fixture_name)

    def build_webhook_url(self):
        # type: () -> text_type
        return ''

    def build_url(self, fixture_name):
        # type: (text_type) -> text_type
        return self.URL_TEMPLATE.format(payload=self.get_payload(fixture_name), stream=self.STREAM_NAME)
