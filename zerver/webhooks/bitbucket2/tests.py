from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

TOPIC = "Repository name"
TOPIC_PR_EVENTS = "Repository name / PR #1 new commit"
TOPIC_ISSUE_EVENTS = "Repository name / Issue #1 Bug"
TOPIC_BRANCH_EVENTS = "Repository name / master"

class Bitbucket2HookTests(WebhookTestCase):
    STREAM_NAME = 'bitbucket2'
    URL_TEMPLATE = "/api/v1/external/bitbucket2?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'bitbucket2'

    def test_bitbucket2_on_push_event(self) -> None:
        commit_info = '* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))'
        expected_message = f"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n{commit_info}"
        self.check_webhook("push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers(self) -> None:
        commit_info = '* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = f"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 3 commits to branch master. Commits by zbenjamin (2) and kolaszek (1).\n\n{commit_info*2}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook("push_multiple_committers", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_with_others(self) -> None:
        commit_info = '* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = f"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 10 commits to branch master. Commits by james (3), Brendon (2), Tomasz (2) and others (3).\n\n{commit_info*9}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook(
            "push_multiple_committers_with_others", TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket2_on_push_commits_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = '* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = f"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 3 commits to branch master. Commits by zbenjamin (2) and kolaszek (1).\n\n{commit_info*2}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook("push_multiple_committers", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_with_others_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = '* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n'
        expected_message = f"""kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 10 commits to branch master. Commits by james (3), Brendon (2), Tomasz (2) and others (3).\n\n{commit_info*9}* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook(
            "push_multiple_committers_with_others", TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket2_on_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = '* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))'
        expected_message = f"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n{commit_info}"
        self.check_webhook("push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_event(self) -> None:
        commit_info = '* a ([6f161a7](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0))\n'
        expected_message = f"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) 5 commits to branch master. Commits by Tomasz (5).\n\n{(commit_info * 5)}[and more commit(s)]"
        self.check_webhook("push_commits_above_limit", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        commit_info = '* a ([6f161a7](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0))\n'
        expected_message = f"kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) 5 commits to branch master. Commits by Tomasz (5).\n\n{(commit_info * 5)}[and more commit(s)]"

        self.check_webhook("push_commits_above_limit", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event(self) -> None:
        expected_message = "kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12."
        self.check_webhook("force_push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        expected_message = "kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12."
        self.check_webhook("force_push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_remove_branch_event(self) -> None:
        expected_message = "kolaszek deleted branch master."
        self.check_webhook("remove_branch", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_fork_event(self) -> None:
        expected_message = "User Tomasz(login: kolaszek) forked the repository into [kolaszek/repository-name2](https://bitbucket.org/kolaszek/repository-name2)."
        self.check_webhook("fork", TOPIC, expected_message)

    def test_bitbucket2_on_commit_comment_created_event(self) -> None:
        expected_message = "kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74#comment-3354963) on [32c4ea1](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74):\n~~~ quote\nNice fix!\n~~~"
        self.check_webhook("commit_comment_created", TOPIC, expected_message)

    def test_bitbucket2_on_commit_status_changed_event(self) -> None:
        expected_message = "[System mybuildtool](https://my-build-tool.com/builds/MY-PROJECT/BUILD-777) changed status of [9fec847](https://bitbucket.org/kolaszek/repository-name/commits/9fec847784abb10b2fa567ee63b85bd238955d0e) to SUCCESSFUL."
        self.check_webhook("commit_status_changed", TOPIC, expected_message)

    def test_bitbucket2_on_issue_created_event(self) -> None:
        expected_message = "kolaszek created [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug) (assigned to kolaszek):\n\n~~~ quote\nSuch a bug\n~~~"
        self.check_webhook("issue_created", TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "kolaszek created [Issue #1 Bug](https://bitbucket.org/kolaszek/repository-name/issues/2/bug) (assigned to kolaszek):\n\n~~~ quote\nSuch a bug\n~~~"
        self.check_webhook("issue_created", expected_topic, expected_message)

    def test_bitbucket2_on_issue_updated_event(self) -> None:
        expected_message = "kolaszek updated [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)."
        self.check_webhook("issue_updated", TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_event(self) -> None:
        expected_message = "kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [Issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)."
        self.check_webhook("issue_commented", TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [Issue #1 Bug](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)."
        self.check_webhook("issue_commented", expected_topic, expected_message)

    def test_bitbucket2_on_pull_request_created_event(self) -> None:
        expected_message = "kolaszek created [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) (assigned to tkolek) from `new-branch` to `master`:\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created',
        }
        self.check_webhook(
            "pull_request_created_or_updated", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_created_without_reviewer_username_event(self) -> None:
        expected_message = "kolaszek created [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) (assigned to Tomasz Kolek) from `new-branch` to `master`:\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created',
        }
        self.check_webhook(
            "pull_request_created_or_updated_without_username",
            TOPIC_PR_EVENTS,
            expected_message,
            **kwargs
        )

    def test_bitbucket2_on_pull_request_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "kolaszek created [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) (assigned to tkolek) from `new-branch` to `master`:\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:created',
        }
        self.check_webhook(
            "pull_request_created_or_updated", expected_topic, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_updated_event(self) -> None:
        expected_message = "kolaszek updated [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) (assigned to tkolek) from `new-branch` to `master`:\n\n~~~ quote\ndescription\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:updated',
        }
        self.check_webhook(
            "pull_request_created_or_updated", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_approved_event(self) -> None:
        expected_message = "kolaszek approved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:approved',
        }
        self.check_webhook(
            "pull_request_approved_or_unapproved", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_approved_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "kolaszek approved [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:approved',
        }
        self.check_webhook(
            "pull_request_approved_or_unapproved", expected_topic, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_unapproved_event(self) -> None:
        expected_message = "kolaszek unapproved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:unapproved',
        }
        self.check_webhook(
            "pull_request_approved_or_unapproved", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_declined_event(self) -> None:
        expected_message = "kolaszek rejected [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:rejected',
        }
        self.check_webhook(
            "pull_request_fulfilled_or_rejected", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_fulfilled_event(self) -> None:
        expected_message = "kolaszek merged [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:fulfilled',
        }
        self.check_webhook(
            "pull_request_fulfilled_or_rejected", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_comment_created_event(self) -> None:
        expected_message = "kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_created',
        }
        self.check_webhook(
            "pull_request_comment_action", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_comment_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "kolaszek [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_created',
        }
        self.check_webhook(
            "pull_request_comment_action", expected_topic, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_comment_updated_event(self) -> None:
        expected_message = "kolaszek updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_updated',
        }
        self.check_webhook(
            "pull_request_comment_action", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_comment_updated_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic = "notifications"
        expected_message = "kolaszek updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_updated',
        }
        self.check_webhook(
            "pull_request_comment_action", expected_topic, expected_message, **kwargs
        )

    def test_bitbucket2_on_pull_request_comment_deleted_event(self) -> None:
        expected_message = "kolaszek deleted a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:comment_deleted',
        }
        self.check_webhook(
            "pull_request_comment_action", TOPIC_PR_EVENTS, expected_message, **kwargs
        )

    def test_bitbucket2_on_repo_updated_event(self) -> None:
        expected_message = "eeshangarg changed the website of the **new-name** repo to **http://zulipchat.com**.\neeshangarg changed the name of the **new-name** repo from **test-repo** to **new-name**.\neeshangarg changed the language of the **new-name** repo to **python**.\neeshangarg changed the full name of the **new-name** repo from **webhooktest/test-repo** to **webhooktest/new-name**.\neeshangarg changed the description of the **new-name** repo to **Random description.**"
        expected_topic = "new-name"
        kwargs = {"HTTP_X_EVENT_KEY": 'repo:updated'}
        self.check_webhook("repo_updated", expected_topic, expected_message, **kwargs)

    def test_bitbucket2_on_push_one_tag_event(self) -> None:
        expected_message = "kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push',
        }
        self.check_webhook("push_one_tag", TOPIC, expected_message, **kwargs)

    def test_bitbucket2_on_push_remove_tag_event(self) -> None:
        expected_message = "kolaszek removed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push',
        }
        self.check_webhook("push_remove_tag", TOPIC, expected_message, **kwargs)

    def test_bitbucket2_on_push_more_than_one_tag_event(self) -> None:
        expected_message = "kolaszek pushed tag [{name}](https://bitbucket.org/kolaszek/repository-name/commits/tag/{name})."
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push',
        }

        self.subscribe(self.test_user, self.STREAM_NAME)
        payload = self.get_body("push_more_than_one_tag")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
            **kwargs,
        )

        msg = self.get_second_to_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=TOPIC,
            content=expected_message.format(name="a"),
        )

        msg = self.get_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=TOPIC,
            content=expected_message.format(name="b"),
        )

    def test_bitbucket2_on_more_than_one_push_event(self) -> None:
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push',
        }

        self.subscribe(self.test_user, self.STREAM_NAME)
        payload = self.get_body("more_than_one_push_event")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
            **kwargs,
        )

        msg = self.get_second_to_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=TOPIC_BRANCH_EVENTS,
            content="kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"
        )

        msg = self.get_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=TOPIC,
            content="kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a).",
        )

    def test_bitbucket2_on_more_than_one_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches='master,development')
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push',
        }

        self.subscribe(self.test_user, self.STREAM_NAME)
        payload = self.get_body("more_than_one_push_event")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
            **kwargs,
        )

        msg = self.get_second_to_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=TOPIC_BRANCH_EVENTS,
            content="kolaszek [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n* first commit ([84b96ad](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))",
        )

        msg = self.get_last_message()
        self.assert_stream_message(
            message=msg,
            stream_name=self.STREAM_NAME,
            topic_name=TOPIC,
            content="kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a).",
        )

    def test_bitbucket2_on_more_than_one_push_event_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches='changes,development')
        kwargs = {
            "HTTP_X_EVENT_KEY": 'pullrequest:push',
        }
        expected_message = "kolaszek pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)."
        self.check_webhook("more_than_one_push_event", TOPIC, expected_message, **kwargs)

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
