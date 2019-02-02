# -*- coding: utf-8 -*-
from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT

class GogsHookTests(WebhookTestCase):
    STREAM_NAME = 'commits'
    URL_TEMPLATE = "/api/v1/external/gogs?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'gogs'

    def test_push(self) -> None:
        expected_topic = u"try-git / master"
        expected_message = u"""john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 1 commit to branch master. Commits by John (1).

* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))"""
        self.send_and_test_stream_message('push', expected_topic, expected_message, HTTP_X_GOGS_EVENT='push')

    def test_push_multiple_committers(self) -> None:
        commit_info = u'* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n'
        expected_topic = u"try-git / master"
        expected_message = u"""john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 2 commits to branch master. Commits by Benjamin (1) and John (1).\n\n{}* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))""".format(commit_info)
        self.send_and_test_stream_message('push_commits_multiple_committers', expected_topic, expected_message, HTTP_X_GOGS_EVENT='push')

    def test_push_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = u'* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n'
        expected_topic = u"try-git / master"
        expected_message = u"""john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 2 commits to branch master. Commits by Benjamin (1) and John (1).\n\n{}* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))""".format(commit_info)
        self.send_and_test_stream_message('push_commits_multiple_committers', expected_topic, expected_message, HTTP_X_GOGS_EVENT='push')

    def test_push_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        expected_topic = u"try-git / master"
        expected_message = u"""john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 1 commit to branch master. Commits by John (1).

* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))"""
        self.send_and_test_stream_message('push', expected_topic, expected_message, HTTP_X_GOGS_EVENT='push')

    def test_push_commits_more_than_limits(self) -> None:
        expected_topic = u"try-git / master"
        commits_info = "* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n"
        expected_message = u"john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 30 commits to branch master. Commits by John (30).\n\n{}[and {} more commit(s)]".format(
            commits_info * COMMITS_LIMIT,
            30 - COMMITS_LIMIT
        )
        self.send_and_test_stream_message('push_commits_more_than_limits', expected_topic, expected_message, HTTP_X_GOGS_EVENT='push')

    def test_push_commits_more_than_limits_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        expected_topic = u"try-git / master"
        commits_info = "* Webhook Test ([d8fce16](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n"
        expected_message = u"john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 30 commits to branch master. Commits by John (30).\n\n{}[and {} more commit(s)]".format(
            commits_info * COMMITS_LIMIT,
            30 - COMMITS_LIMIT
        )
        self.send_and_test_stream_message('push_commits_more_than_limits', expected_topic, expected_message, HTTP_X_GOGS_EVENT='push')

    def test_new_branch(self) -> None:
        expected_topic = u"try-git / my_feature"
        expected_message = u"john created [my_feature](http://localhost:3000/john/try-git/src/my_feature) branch"
        self.send_and_test_stream_message('branch', expected_topic, expected_message, HTTP_X_GOGS_EVENT='create')

    def test_pull_request_opened(self) -> None:
        expected_topic = u"try-git / PR #1 Title Text for Pull Request"
        expected_message = u"""john opened [PR #1](http://localhost:3000/john/try-git/pulls/1)
from `feature` to `master`"""
        self.send_and_test_stream_message('pull_request_opened', expected_topic, expected_message, HTTP_X_GOGS_EVENT='pull_request')

    def test_pull_request_opened_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic='notifications')
        expected_topic = u"notifications"
        expected_message = u"""john opened [PR #1 Title Text for Pull Request](http://localhost:3000/john/try-git/pulls/1)
from `feature` to `master`"""
        self.send_and_test_stream_message('pull_request_opened', expected_topic, expected_message, HTTP_X_GOGS_EVENT='pull_request')

    def test_pull_request_closed(self) -> None:
        expected_topic = u"try-git / PR #1 Title Text for Pull Request"
        expected_message = u"""john closed [PR #1](http://localhost:3000/john/try-git/pulls/1)
from `feature` to `master`"""
        self.send_and_test_stream_message('pull_request_closed', expected_topic, expected_message, HTTP_X_GOGS_EVENT='pull_request')

    def test_pull_request_merged(self) -> None:
        expected_topic = u"try-git / PR #2 Title Text for Pull Request"
        expected_message = u"""john merged [PR #2](http://localhost:3000/john/try-git/pulls/2)
from `feature` to `master`"""
        self.send_and_test_stream_message('pull_request_merged', expected_topic, expected_message, HTTP_X_GOGS_EVENT='pull_request')

    @patch('zerver.webhooks.gogs.view.check_send_webhook_message')
    def test_push_filtered_by_branches_ignore(self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('push')
        result = self.client_post(self.url, payload, HTTP_X_GOGS_EVENT='push',
                                  content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.gogs.view.check_send_webhook_message')
    def test_push_commits_more_than_limits_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('push_commits_more_than_limits')
        result = self.client_post(self.url, payload, HTTP_X_GOGS_EVENT='push',
                                  content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.gogs.view.check_send_webhook_message')
    def test_push_multiple_committers_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,development')
        payload = self.get_body('push_commits_multiple_committers')
        result = self.client_post(self.url, payload, HTTP_X_GOGS_EVENT='push',
                                  content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)
