# -*- coding: utf-8 -*-
from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

class Bitbucket2HookTests(WebhookTestCase):
    STREAM_NAME = 'bitbucket2'
    URL_TEMPLATE = "/api/v1/external/bitbucket2?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'bitbucket2'
    EXPECTED_TOPIC = u"Repository name"
    EXPECTED_TOPIC_PR_EVENTS = u"Repository name / PR #1 new commit"
    EXPECTED_TOPIC_ISSUE_EVENTS = u"Repository name / Issue #1 Bug"
    EXPECTED_TOPIC_BRANCH_EVENTS = u"Repository name / master"

    def test_bitbucket2_on_push_event(self) -> None:
        commit_info = u'* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))'
        expected_message = u"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n{}".format(commit_info)
        self.send_and_test_stream_message('push', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers(self) -> None:
        commit_info = u'* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = u"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 3 commits to branch master. Commits by zbenjamin (2) and kolaszek (1).\n\n{}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))""".format(commit_info*2)
        self.send_and_test_stream_message('push_multiple_committers', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_with_others(self) -> None:
        commit_info = u'* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = u"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 10 commits to branch master. Commits by james (3), Brendon (2), Tomasz (2) and others (3).\n\n{}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))""".format(commit_info*9)
        self.send_and_test_stream_message('push_multiple_committers_with_others', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = u'* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = u"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 3 commits to branch master. Commits by zbenjamin (2) and kolaszek (1).\n\n{}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))""".format(commit_info*2)
        self.send_and_test_stream_message('push_multiple_committers', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_with_others_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = u'* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = u"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 10 commits to branch master. Commits by james (3), Brendon (2), Tomasz (2) and others (3).\n\n{}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))""".format(commit_info*9)
        self.send_and_test_stream_message('push_multiple_committers_with_others', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = u'* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))'
        expected_message = u"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n{}".format(commit_info)
        self.send_and_test_stream_message('push', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_event(self) -> None:
        commit_info = '* a ([6f161a7](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0))\n'
        expected_message = u"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) 5 commits to branch master. Commits by Tomasz (5).\n\n{}[and more commit(s)]".format(
            (commit_info * 5),
        )
        self.send_and_test_stream_message('push_commits_above_limit', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = '* a ([6f161a7](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0))\n'
        expected_message = u"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) 5 commits to branch master. Commits by Tomasz (5).\n\n{}[and more commit(s)]".format(
            (commit_info * 5),
        )
        self.send_and_test_stream_message('push_commits_above_limit', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event(self) -> None:
        expected_message = u"kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12"
        self.send_and_test_stream_message('force_push', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        expected_message = u"kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12"
        self.send_and_test_stream_message('force_push', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_remove_branch_event(self) -> None:
        expected_message = u"kolaszek deleted branch master"
        self.send_and_test_stream_message('remove_branch', self.EXPECTED_TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_fork_event(self) -> None:
        expected_message = u"User Tomasz(login: kolaszek) forked the repository into [kolaszek/repository-name2](https://bitbucket.org/kolaszek/repository-name2)."
        self.send_and_test_stream_message('fork', self.EXPECTED_TOPIC, expected_message)

    def test_bitbucket2_on_commit_comment_created_event(self) -> None:
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74#comment-3354963) on [32c4ea1](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74)\n~~~ quote\nNice fix!\n~~~"
        self.send_and_test_stream_message('commit_comment_created', self.EXPECTED_TOPIC, expected_message)

    def test_bitbucket2_on_commit_status_changed_event(self) -> None:
        expected_message = u"[System mybuildtool](https://my-build-tool.com/builds/MY-PROJECT/BUILD-777) changed status of [9fec847](https://bitbucket.org/kolaszek/repository-name/commits/9fec847784abb10b2fa567ee63b85bd238955d0e) to SUCCESSFUL."
        self.send_and_test_stream_message('commit_status_changed', self.EXPECTED_TOPIC, expected_message)

    def test_bitbucket2_on_issue_created_event(self) -> None:
        expected_message = u"kolaszek created [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)(assigned to kolaszek)\n\n~~~ quote\nSuch a bug\n~~~"
        self.send_and_test_stream_message('issue_created', self.EXPECTED_TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = u"notifications"
        expected_message = u"kolaszek created [Issue #1 Bug](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)(assigned to kolaszek)\n\n~~~ quote\nSuch a bug\n~~~"
        self.send_and_test_stream_message('issue_created', expected_topic, expected_message)

    def test_bitbucket2_on_issue_updated_event(self) -> None:
        expected_message = u"kolaszek updated [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('issue_updated', self.EXPECTED_TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_event(self) -> None:
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('issue_commented', self.EXPECTED_TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = u"notifications"
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [Issue #1 Bug](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)"
        self.send_and_test_stream_message('issue_commented', expected_topic, expected_message)

    def test_bitbucket2_on_pull_request_created_event(self) -> None:
        expected_message = u"kolaszek created [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)(assigned to tkolek)\nfrom `new-branch` to `master`\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created'
        }
        self.send_and_test_stream_message('pull_request_created_or_updated', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = u"notifications"
        expected_message = u"kolaszek created [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)(assigned to tkolek)\nfrom `new-branch` to `master`\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created'
        }
        self.send_and_test_stream_message('pull_request_created_or_updated', expected_topic, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_updated_event(self) -> None:
        expected_message = u"kolaszek updated [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)(assigned to tkolek)\nfrom `new-branch` to `master`\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:updated'
        }
        self.send_and_test_stream_message('pull_request_created_or_updated', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_approved_event(self) -> None:
        expected_message = u"kolaszek approved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:approved'
        }
        self.send_and_test_stream_message('pull_request_approved_or_unapproved', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_approved_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = u"notifications"
        expected_message = u"kolaszek approved [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:approved'
        }
        self.send_and_test_stream_message('pull_request_approved_or_unapproved', expected_topic, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_unapproved_event(self) -> None:
        expected_message = u"kolaszek unapproved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:unapproved'
        }
        self.send_and_test_stream_message('pull_request_approved_or_unapproved', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_declined_event(self) -> None:
        expected_message = u"kolaszek rejected [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:rejected'
        }
        self.send_and_test_stream_message('pull_request_fulfilled_or_rejected', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_fulfilled_event(self) -> None:
        expected_message = u"kolaszek merged [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:fulfilled'
        }
        self.send_and_test_stream_message('pull_request_fulfilled_or_rejected', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_created_event(self) -> None:
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_created'
        }
        self.send_and_test_stream_message('pull_request_comment_action', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = u"notifications"
        expected_message = u"kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_created'
        }
        self.send_and_test_stream_message('pull_request_comment_action', expected_topic, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_updated_event(self) -> None:
        expected_message = u"kolaszek updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_updated'
        }
        self.send_and_test_stream_message('pull_request_comment_action', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_updated_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = u"notifications"
        expected_message = u"kolaszek updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_updated'
        }
        self.send_and_test_stream_message('pull_request_comment_action', expected_topic, expected_message, **kwargs)

    def test_bitbucket2_on_pull_request_comment_deleted_event(self) -> None:
        expected_message = u"kolaszek deleted a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3)\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_deleted'
        }
        self.send_and_test_stream_message('pull_request_comment_action', self.EXPECTED_TOPIC_PR_EVENTS, expected_message, **kwargs)

    def test_bitbucket2_on_repo_updated_event(self) -> None:
        expected_message = u"eeshangarg changed the website of the **new-name** repo to **http://zulipchat.com**\neeshangarg changed the name of the **new-name** repo from **test-repo** to **new-name**\neeshangarg changed the language of the **new-name** repo to **python**\neeshangarg changed the full name of the **new-name** repo from **webhooktest/test-repo** to **webhooktest/new-name**\neeshangarg changed the description of the **new-name** repo to **Random description.**"
        expected_topic = u"new-name"
        kwargs = {"HTTP_X_EVENT_KEY": 'repo:updated'}
        self.send_and_test_stream_message('repo_updated', expected_topic,
                                          expected_message, **kwargs)

    def test_bitbucket2_on_push_one_tag_event(self) -> None:
        expected_message = u"kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('push_one_tag', self.EXPECTED_TOPIC, expected_message, **kwargs)

    def test_bitbucket2_on_push_remove_tag_event(self) -> None:
        expected_message = u"kolaszek removed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('push_remove_tag', self.EXPECTED_TOPIC, expected_message, **kwargs)

    def test_bitbucket2_on_push_more_than_one_tag_event(self) -> None:
        expected_message = u"kolaszek pushed tag [{name}](https://bitbucket.org/kolaszek/repository-name/commits/tag/{name})"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('push_more_than_one_tag', **kwargs)
        msg = self.get_last_message()
        self.do_test_topic(msg, self.EXPECTED_TOPIC)
        self.do_test_message(msg, expected_message.format(name='b'))
        msg = self.get_second_to_last_message()
        self.do_test_topic(msg, self.EXPECTED_TOPIC)
        self.do_test_message(msg, expected_message.format(name='a'))

    def test_bitbucket2_on_more_than_one_push_event(self) -> None:
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('more_than_one_push_event', **kwargs)
        msg = self.get_second_to_last_message()
        self.do_test_message(msg, 'kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))')
        self.do_test_topic(msg, self.EXPECTED_TOPIC_BRANCH_EVENTS)
        msg = self.get_last_message()
        self.do_test_message(msg, 'kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)')
        self.do_test_topic(msg, self.EXPECTED_TOPIC)

    def test_bitbucket2_on_more_than_one_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        self.send_and_test_stream_message('more_than_one_push_event', **kwargs)
        msg = self.get_second_to_last_message()
        self.do_test_message(msg, 'kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))')
        self.do_test_topic(msg, self.EXPECTED_TOPIC_BRANCH_EVENTS)
        msg = self.get_last_message()
        self.do_test_message(msg, 'kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)')
        self.do_test_topic(msg, self.EXPECTED_TOPIC)

    def test_bitbucket2_on_more_than_one_push_event_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches='changes,development')
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push'
        }
        expected_message = u"kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)"
        self.send_and_test_stream_message('more_than_one_push_event',
                                          self.EXPECTED_TOPIC,
                                          expected_message, **kwargs)

    @patch('zerver.webhooks.bitbucket2.view.check_send_webhook_message')
    def test_bitbucket2_on_push_event_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,devlopment')
        payload = self.get_body('push')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.bitbucket2.view.check_send_webhook_message')
    def test_bitbucket2_on_push_commits_above_limit_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,devlopment')
        payload = self.get_body('push_commits_above_limit')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.bitbucket2.view.check_send_webhook_message')
    def test_bitbucket2_on_force_push_event_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,devlopment')
        payload = self.get_body('force_push')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.bitbucket2.view.check_send_webhook_message')
    def test_bitbucket2_on_push_multiple_committers_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,devlopment')
        payload = self.get_body('push_multiple_committers')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.bitbucket2.view.check_send_webhook_message')
    def test_bitbucket2_on_push_multiple_committers_with_others_filtered_by_branches_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url(branches='changes,devlopment')
        payload = self.get_body('push_multiple_committers_with_others')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch('zerver.webhooks.bitbucket2.view.check_send_webhook_message')
    def test_bitbucket2_on_push_without_changes_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        payload = self.get_body('push_without_changes')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)
