import ujson
from mock import patch, MagicMock
from typing import Dict, Optional, Text

from zerver.models import Message
from zerver.lib.webhooks.git import COMMITS_LIMIT
from zerver.lib.test_classes import WebhookTestCase

class GithubWebhookTest(WebhookTestCase):
    STREAM_NAME = 'github'
    URL_TEMPLATE = "/api/v1/external/github?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'github_webhook'
    EXPECTED_SUBJECT_REPO_EVENTS = u"public-repo"
    EXPECTED_SUBJECT_ISSUE_EVENTS = u"public-repo / Issue #2 Spelling error in the README file"
    EXPECTED_SUBJECT_PR_EVENTS = u"public-repo / PR #1 Update the README with new information"
    EXPECTED_SUBJECT_DEPLOYMENT_EVENTS = u"public-repo / Deployment on production"
    EXPECTED_SUBJECT_ORGANIZATION_EVENTS = u"baxterandthehackers organization"
    EXPECTED_SUBJECT_BRANCH_EVENTS = u"public-repo / changes"
    EXPECTED_SUBJECT_WIKI_EVENTS = u"public-repo / Wiki Pages"

    def test_ping_event(self):
        # type: () -> None
        payload = self.get_body('ping')
        result = self.client_post(self.url, payload, HTTP_X_GITHUB_EVENT='ping', content_type="application/json")
        self.assert_json_success(result)

    def test_push_1_commit(self):
        # type: () -> None
        expected_message = u"baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) to branch changes\n\n* [0d1a26e](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c): Update README.md"
        self.send_and_test_stream_message('push_1_commit', self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='push')

    def test_push_50_commits(self):
        # type: () -> None
        commit_info = "* [0d1a26e](https://github.com/baxterthehacker/public-repo/commit/0d1a26e67d8f5eaf1f6ba5c57fc3c7d91ac0fd1c): Update README.md\n"
        expected_message = u"baxterthehacker [pushed](https://github.com/baxterthehacker/public-repo/compare/9049f1265b7d...0d1a26e67d8f) to branch changes\n\n{}[and 30 more commit(s)]".format(
            commit_info * COMMITS_LIMIT
        )
        self.send_and_test_stream_message('push_50_commits', self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='push')

    def test_commit_comment_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker [commented](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b#commitcomment-11056394) on [9049f12](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b)\n~~~ quote\nThis is a really good change! :+1:\n~~~"
        self.send_and_test_stream_message('commit_comment', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='commit_comment')

    def test_create_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker created tag 0.0.1"
        self.send_and_test_stream_message('create', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='create')

    def test_delete_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker deleted tag simple-tag"
        self.send_and_test_stream_message('delete', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='delete')

    def test_deployment_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker created new deployment"
        self.send_and_test_stream_message('deployment', self.EXPECTED_SUBJECT_DEPLOYMENT_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='deployment')

    def test_deployment_status_msg(self):
        # type: () -> None
        expected_message = u"Deployment changed status to success"
        self.send_and_test_stream_message('deployment_status', self.EXPECTED_SUBJECT_DEPLOYMENT_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='deployment_status')

    def test_fork_msg(self):
        # type: () -> None
        expected_message = u"baxterandthehackers forked [public-repo](https://github.com/baxterandthehackers/public-repo)"
        self.send_and_test_stream_message('fork', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='fork')

    def test_issue_comment_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker [commented](https://github.com/baxterthehacker/public-repo/issues/2#issuecomment-99262140) on [Issue #2](https://github.com/baxterthehacker/public-repo/issues/2)\n\n~~~ quote\nYou are totally right! I'll get this fixed right away.\n~~~"
        self.send_and_test_stream_message('issue_comment', self.EXPECTED_SUBJECT_ISSUE_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='issue_comment')

    def test_issue_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker opened [Issue #2](https://github.com/baxterthehacker/public-repo/issues/2)\n\n~~~ quote\nIt looks like you accidently spelled 'commit' with two 't's.\n~~~"
        self.send_and_test_stream_message('issue', self.EXPECTED_SUBJECT_ISSUE_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='issue')

    def test_membership_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker added [kdaigle](https://github.com/kdaigle) to Contractors team"
        self.send_and_test_stream_message('membership', self.EXPECTED_SUBJECT_ORGANIZATION_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='membership')

    def test_member_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker added [octocat](https://github.com/octocat) to [public-repo](https://github.com/baxterthehacker/public-repo)"
        self.send_and_test_stream_message('member', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='member')

    def test_pull_request_opened_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker opened [PR](https://github.com/baxterthehacker/public-repo/pull/1)\nfrom `changes` to `master`\n\n~~~ quote\nThis is a pretty simple change that we need to pull into master.\n~~~"
        self.send_and_test_stream_message('opened_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='pull_request')

    def test_pull_request_synchronized_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker updated [PR](https://github.com/baxterthehacker/public-repo/pull/1)\nfrom `changes` to `master`"
        self.send_and_test_stream_message('synchronized_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='pull_request')

    def test_pull_request_closed_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker closed without merge [PR](https://github.com/baxterthehacker/public-repo/pull/1)"
        self.send_and_test_stream_message('closed_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='pull_request')

    def test_pull_request_merged_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker merged [PR](https://github.com/baxterthehacker/public-repo/pull/1)"
        self.send_and_test_stream_message('merged_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='pull_request')

    def test_public_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker made [the repository](https://github.com/baxterthehacker/public-repo) public"
        self.send_and_test_stream_message('public', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='public')

    def test_wiki_pages_msg(self):
        # type: () -> None
        expected_message = u"jasonrudolph:\n* created [Home](https://github.com/baxterthehacker/public-repo/wiki/Home)\n* created [Home](https://github.com/baxterthehacker/public-repo/wiki/Home)"
        self.send_and_test_stream_message('wiki_pages', self.EXPECTED_SUBJECT_WIKI_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='gollum')

    def test_watch_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker starred [the repository](https://github.com/baxterthehacker/public-repo)"
        self.send_and_test_stream_message('watch_repository', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='watch')

    def test_repository_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker created [the repository](https://github.com/baxterandthehackers/public-repo)"
        self.send_and_test_stream_message('repository', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='repository')

    def test_team_add_msg(self):
        # type: () -> None
        expected_message = u"[The repository](https://github.com/baxterandthehackers/public-repo) was added to team github"
        self.send_and_test_stream_message('team_add', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='team_add')

    def test_release_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker published [the release](https://github.com/baxterthehacker/public-repo/releases/tag/0.0.1)"
        self.send_and_test_stream_message('release', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='release')

    def test_page_build_msg(self):
        # type: () -> None
        expected_message = u"Github Pages build, trigerred by baxterthehacker, is built"
        self.send_and_test_stream_message('page_build', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='page_build')

    def test_status_msg(self):
        # type: () -> None
        expected_message = u"[9049f12](https://github.com/baxterthehacker/public-repo/commit/9049f1265b7d61be4a8904a9a27120d2064dab3b) changed it's status to success"
        self.send_and_test_stream_message('status', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='status')

    def test_pull_request_review_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker submitted [PR Review](https://github.com/baxterthehacker/public-repo/pull/1#pullrequestreview-2626884)"
        self.send_and_test_stream_message('pull_request_review', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='pull_request_review')

    def test_pull_request_review_comment_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker created [PR Review Comment](https://github.com/baxterthehacker/public-repo/pull/1#discussion_r29724692)\n\n~~~ quote\nMaybe you should use more emojji on this line.\n~~~"
        self.send_and_test_stream_message('pull_request_review_comment', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='pull_request_review_comment')

    def test_push_tag_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker pushed tag abc"
        self.send_and_test_stream_message('push_tag', self.EXPECTED_SUBJECT_REPO_EVENTS, expected_message, HTTP_X_GITHUB_EVENT='push')

    def test_pull_request_edited_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker edited [PR](https://github.com/baxterthehacker/public-repo/pull/1)\nfrom `changes` to `master`"
        self.send_and_test_stream_message('edited_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message,
                                          HTTP_X_GITHUB_EVENT='pull_request')

    def test_pull_request_assigned_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker assigned [PR](https://github.com/baxterthehacker/public-repo/pull/1) to baxterthehacker"
        self.send_and_test_stream_message('assigned_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message,
                                          HTTP_X_GITHUB_EVENT='pull_request')

    def test_pull_request_unassigned_msg(self):
        # type: () -> None
        expected_message = u"baxterthehacker unassigned [PR](https://github.com/baxterthehacker/public-repo/pull/1)"
        self.send_and_test_stream_message('unassigned_pull_request', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message,
                                          HTTP_X_GITHUB_EVENT='pull_request')

    @patch('zerver.webhooks.github_webhook.view.check_send_message')
    def test_pull_request_labeled_ignore(self, check_send_message_mock):
        # type: (MagicMock) -> None
        payload = self.get_body('labeled_pull_request')
        result = self.client_post(self.url, payload, HTTP_X_GITHUB_EVENT='pull_request', content_type="application/json")
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.github_webhook.view.check_send_message')
    def test_pull_request_unlabeled_ignore(self, check_send_message_mock):
        # type: (MagicMock) -> None
        payload = self.get_body('unlabeled_pull_request')
        result = self.client_post(self.url, payload, HTTP_X_GITHUB_EVENT='pull_request', content_type="application/json")
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.github_webhook.view.check_send_message')
    def test_pull_request_request_review_ignore(self, check_send_message_mock):
        # type: (MagicMock) -> None
        payload = self.get_body('request_review_pull_request')
        result = self.client_post(self.url, payload, HTTP_X_GITHUB_EVENT='pull_request', content_type="application/json")
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.github_webhook.view.check_send_message')
    def test_pull_request_request_review_remove_ignore(self, check_send_message_mock):
        # type: (MagicMock) -> None
        payload = self.get_body('request_review_removed_pull_request')
        result = self.client_post(self.url, payload, HTTP_X_GITHUB_EVENT='pull_request', content_type="application/json")
        self.assertFalse(check_send_message_mock.called)
        self.assert_json_success(result)
