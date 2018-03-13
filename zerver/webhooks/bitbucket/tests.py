# -*- coding: utf-8 -*-
from typing import Dict, Optional, Text, Union

from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

class BitbucketHookTests(WebhookTestCase):
    STREAM_NAME = 'bitbucket'
    URL_TEMPLATE = "/api/v1/external/bitbucket?stream={stream}"
    FIXTURE_DIR_NAME = 'bitbucket'
    EXPECTED_SUBJECT = u"Repository name"
    EXPECTED_SUBJECT_BRANCH_EVENTS = u"Repository name / master"

    def test_bitbucket_on_push_event(self) -> None:
        fixture_name = 'push'
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        commit_info = u'* c ([25f93d2](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))'
        expected_message = u"kolaszek pushed 1 commit to branch master.\n\n{}".format(commit_info)
        self.api_stream_message(self.TEST_USER_EMAIL, fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS,
                                expected_message)

    def test_bitbucket_on_push_event_filtered_by_branches(self) -> None:
        fixture_name = 'push'
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name),
                                          branches='master,development')
        commit_info = u'* c ([25f93d2](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))'
        expected_message = u"kolaszek pushed 1 commit to branch master.\n\n{}".format(commit_info)
        self.api_stream_message(self.TEST_USER_EMAIL, fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS,
                                expected_message)

    def test_bitbucket_on_push_commits_above_limit_event(self) -> None:
        fixture_name = 'push_commits_above_limit'
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        commit_info = u'* c ([25f93d2](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))\n'
        expected_message = u"kolaszek pushed 50 commits to branch master.\n\n{}[and 30 more commit(s)]".format(commit_info * 20)
        self.api_stream_message(self.TEST_USER_EMAIL, fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS,
                                expected_message)

    def test_bitbucket_on_push_commits_above_limit_event_filtered_by_branches(self) -> None:
        fixture_name = 'push_commits_above_limit'
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name),
                                          branches='master,development')
        commit_info = u'* c ([25f93d2](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))\n'
        expected_message = u"kolaszek pushed 50 commits to branch master.\n\n{}[and 30 more commit(s)]".format(commit_info * 20)
        self.api_stream_message(self.TEST_USER_EMAIL, fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS,
                                expected_message)

    def test_bitbucket_on_force_push_event(self) -> None:
        fixture_name = 'force_push'
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        expected_message = u"kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name)"
        self.api_stream_message(self.TEST_USER_EMAIL, fixture_name, self.EXPECTED_SUBJECT,
                                expected_message)

    @patch('zerver.webhooks.bitbucket.view.check_send_webhook_message')
    def test_bitbucket_on_push_event_filtered_by_branches_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        fixture_name = 'push'
        payload = self.get_body(fixture_name)
        self.url = self.build_webhook_url(payload=payload,
                                          branches='changes,development')
        result = self.api_post(self.TEST_USER_EMAIL, self.url, payload, content_type="application/json,")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.bitbucket.view.check_send_webhook_message')
    def test_bitbucket_push_commits_above_limit_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        fixture_name = 'push_commits_above_limit'
        payload = self.get_body(fixture_name)
        self.url = self.build_webhook_url(payload=payload,
                                          branches='changes,development')
        result = self.api_post(self.TEST_USER_EMAIL, self.url, payload, content_type="application/json,")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def get_body(self, fixture_name: Text) -> Union[Text, Dict[str, Text]]:
        return self.fixture_data(self.FIXTURE_DIR_NAME, fixture_name)
