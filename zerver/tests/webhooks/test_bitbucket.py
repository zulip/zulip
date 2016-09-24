# -*- coding: utf-8 -*-
from zerver.lib.test_helpers import WebhookTestCase

class Bitbucket2HookTests(WebhookTestCase):
    STREAM_NAME = 'bitbucket2'
    URL_TEMPLATE = "/api/v1/external/bitbucket2?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'bitbucket2'
    EXPECTED_SUBJECT =  u"Repository name"

    def test_bitbucket2_on_push_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) pushed [1 commit](https://bitbucket.org/kolaszek/repository-name/branch/master) into master branch."
        self.send_and_test_stream_message('push', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_fork_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) forked the repository into [kolaszek/repository-name2](https://bitbucket.org/kolaszek/repository-name2)."
        self.send_and_test_stream_message('fork', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_commit_comment_created_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) added [comment](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74#comment-3354963) to commit."
        self.send_and_test_stream_message('commit_comment_created', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_commit_status_changed_event(self):
        # type: () -> None
        expected_message = u"[System mybuildtool](https://my-build-tool.com/builds/MY-PROJECT/BUILD-777) changed status of https://bitbucket.org/kolaszek/repository-name/9fec847784abb10b2fa567ee63b85bd238955d0e to SUCCESSFUL."
        self.send_and_test_stream_message('commit_status_changed', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_issue_created_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) created [an issue](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('issue_created', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_issue_updated_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) updated [an issue](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('issue_updated', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_issue_commented_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) commented [an issue](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('issue_commented', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_pull_request_created_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) created [\"new commit\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created'
        }
        self.send_and_test_stream_message('pull_request_created_or_updated', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_updated_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) updated [\"new commit\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:updated'
        }
        self.send_and_test_stream_message('pull_request_created_or_updated', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_approved_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) approved [\"new commit\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:approved'
        }
        self.send_and_test_stream_message('pull_request_approved_or_unapproved', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_unapproved_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) unapproved [\"new commit\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:unapproved'
        }
        self.send_and_test_stream_message('pull_request_approved_or_unapproved', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_declined_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) rejected [\"new commit\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:rejected'
        }
        self.send_and_test_stream_message('pull_request_merged_or_rejected', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_merged_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) merged [\"new commit\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:merged'
        }
        self.send_and_test_stream_message('pull_request_merged_or_rejected', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_created_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) created [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503 in [\"a\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_created'
        }
        self.send_and_test_stream_message('pull_request_comment_action', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_updated_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) updated [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503 in [\"a\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_updated'
        }
        self.send_and_test_stream_message('pull_request_comment_action', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_deleted_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) deleted [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503 in [\"a\" pull request](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_deleted'
        }
        self.send_and_test_stream_message('pull_request_comment_action', self.EXPECTED_SUBJECT, expected_message, **kwargs)
