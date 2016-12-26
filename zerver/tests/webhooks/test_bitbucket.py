# -*- coding: utf-8 -*-
from typing import Union, Text
from zerver.lib.webhooks.git import COMMITS_LIMIT
from zerver.lib.test_classes import WebhookTestCase

class Bitbucket2HookTests(WebhookTestCase):
    STREAM_NAME = 'bitbucket2'
    URL_TEMPLATE = "/api/v1/external/bitbucket2?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'bitbucket'
    EXPECTED_SUBJECT = u"Repository name"
    EXPECTED_SUBJECT_PR_EVENTS = u"Repository name / PR #1 new commit"
    EXPECTED_SUBJECT_ISSUE_EVENTS = u"Repository name / Issue #1 Bug"
    EXPECTED_SUBJECT_BRANCH_EVENTS = u"Repository name / master"

    def test_bitbucket2_on_push_event(self):
        # type: () -> None
        commit_info = u'* [84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed): first commit'
        expected_message = u"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master\n\n{}".format(commit_info)
        self.send_and_test_stream_message('v2_push', self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_event(self):
        # type: () -> None
        commit_info = '* [6f161a7](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0): a\n'
        expected_message = u"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) to branch master\n\n{}[and more commit(s)]".format(
            (commit_info * 5),
        )
        self.send_and_test_stream_message('v2_push_commits_above_limit', self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event(self):
        # type: () -> None
        expected_message = u"kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12"
        self.send_and_test_stream_message('v2_force_push', self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_remove_branch_event(self):
        # type: () -> None
        expected_message = u"kolaszek deleted branch master"
        self.send_and_test_stream_message('v2_remove_branch', self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_fork_event(self):
        # type: () -> None
        expected_message = u"User Tomasz(login: kolaszek) forked the repository into [kolaszek/repository-name2](https://bitbucket.org/kolaszek/repository-name2)."
        self.send_and_test_stream_message('v2_fork', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_commit_comment_created_event(self):
        # type: () -> None
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74#comment-3354963) on [32c4ea1](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74)\n~~~ quote\nNice fix!\n~~~"
        self.send_and_test_stream_message('v2_commit_comment_created', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_commit_status_changed_event(self):
        # type: () -> None
        expected_message = u"[System mybuildtool](https://my-build-tool.com/builds/MY-PROJECT/BUILD-777) changed status of https://bitbucket.org/kolaszek/repository-name/9fec847784abb10b2fa567ee63b85bd238955d0e to SUCCESSFUL."
        self.send_and_test_stream_message('v2_commit_status_changed', self.EXPECTED_SUBJECT, expected_message)

    def test_bitbucket2_on_issue_created_event(self):
        # type: () -> None
        expected_message = u"kolaszek created [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)(assigned to kolaszek)\n\n~~~ quote\nSuch a bug\n~~~"
        self.send_and_test_stream_message('v2_issue_created', self.EXPECTED_SUBJECT_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_updated_event(self):
        # type: () -> None
        expected_message = u"kolaszek updated [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('v2_issue_updated', self.EXPECTED_SUBJECT_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_event(self):
        # type: () -> None
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('v2_issue_commented', self.EXPECTED_SUBJECT_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_pull_request_created_event(self):
        # type: () -> None
        expected_message = u"kolaszek created [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)(assigned to tkolek)\nfrom `new-branch` to `master`\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created'
        }
        self.send_and_test_stream_message('v2_pull_request_created_or_updated', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_updated_event(self):
        # type: () -> None
        expected_message = u"kolaszek updated [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)(assigned to tkolek)\nfrom `new-branch` to `master`\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:updated'
        }
        self.send_and_test_stream_message('v2_pull_request_created_or_updated', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_approved_event(self):
        # type: () -> None
        expected_message = u"kolaszek approved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:approved'
        }
        self.send_and_test_stream_message('v2_pull_request_approved_or_unapproved', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_unapproved_event(self):
        # type: () -> None
        expected_message = u"kolaszek unapproved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:unapproved'
        }
        self.send_and_test_stream_message('v2_pull_request_approved_or_unapproved', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_declined_event(self):
        # type: () -> None
        expected_message = u"kolaszek rejected [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:rejected'
        }
        self.send_and_test_stream_message('v2_pull_request_merged_or_rejected', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_merged_event(self):
        # type: () -> None
        expected_message = u"kolaszek merged [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:merged'
        }
        self.send_and_test_stream_message('v2_pull_request_merged_or_rejected', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_created_event(self):
        # type: () -> None
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_created'
        }
        self.send_and_test_stream_message('v2_pull_request_comment_action', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_updated_event(self):
        # type: () -> None
        expected_message = u"kolaszek updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_updated'
        }
        self.send_and_test_stream_message('v2_pull_request_comment_action', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_deleted_event(self):
        # type: () -> None
        expected_message = u"kolaszek deleted a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_deleted'
        }
        self.send_and_test_stream_message('v2_pull_request_comment_action', self.EXPECTED_SUBJECT_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_push_one_tag_event(self):
        # type: () -> None
        expected_message = u"kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('v2_push_one_tag', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_push_remove_tag_event(self):
        # type: () -> None
        expected_message = u"kolaszek removed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('v2_push_remove_tag', self.EXPECTED_SUBJECT, expected_message, **kwargs)

    def test_bitbucket2_on_push_more_than_one_tag_event(self):
        # type: () -> None
        expected_message = u"kolaszek pushed tag [{name}](https://bitbucket.org/kolaszek/repository-name/commits/tag/{name})"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('v2_push_more_than_one_tag', **kwargs)
        msg = self.get_last_message()
        self.do_test_subject(msg, self.EXPECTED_SUBJECT)
        self.do_test_message(msg, expected_message.format(name='b'))
        msg = self.get_second_to_last_message()
        self.do_test_subject(msg, self.EXPECTED_SUBJECT)
        self.do_test_message(msg, expected_message.format(name='a'))

    def test_bitbucket2_on_more_than_one_push_event(self):
        # type: () -> None
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('v2_more_than_one_push_event', **kwargs)
        msg = self.get_second_to_last_message()
        self.do_test_message(msg, 'kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master\n\n* [84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed): first commit')
        self.do_test_subject(msg, self.EXPECTED_SUBJECT_BRANCH_EVENTS)
        msg = self.get_last_message()
        self.do_test_message(msg, 'kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)')
        self.do_test_subject(msg, self.EXPECTED_SUBJECT)

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
        expected_message = u"kolaszek pushed to branch master\n\n{}[and 40 more commit(s)]".format(commit_info * 10)
        self.send_and_test_stream_message(fixture_name, self.EXPECTED_SUBJECT_BRANCH_EVENTS, expected_message, **self.api_auth(self.TEST_USER_EMAIL))

    def test_bitbucket_on_force_push_event(self):
        # type: () -> None
        fixture_name = 'force_push'
        self.url = self.build_url(fixture_name)
        expected_message = u"kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name)"
        self.send_and_test_stream_message(fixture_name, self.EXPECTED_SUBJECT, expected_message, **self.api_auth(self.TEST_USER_EMAIL))

    def get_body(self, fixture_name):
        # type: (Text) -> Union[Text, Dict[str, Text]]
        return {}

    def get_payload(self, fixture_name):
        # type: (Text) -> Union[Text, Dict[str, Text]]
        return self.fixture_data(self.FIXTURE_DIR_NAME, fixture_name)

    def build_webhook_url(self):
        # type: () -> Text
        return ''

    def build_url(self, fixture_name):
        # type: (Text) -> Text
        return self.URL_TEMPLATE.format(payload=self.get_payload(fixture_name), stream=self.STREAM_NAME)
