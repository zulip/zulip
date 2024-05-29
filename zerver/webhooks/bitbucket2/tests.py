from unittest.mock import MagicMock, patch

from zerver.lib.request import RequestNotes
from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.validator import wrap_wild_value
from zerver.models.clients import get_client
from zerver.webhooks.bitbucket2.view import get_user_info

TOPIC = "Repository name"
TOPIC_PR_EVENTS = "Repository name / PR #1 new commit"
TOPIC_ISSUE_EVENTS = "Repository name / issue #1 Bug"
TOPIC_BRANCH_EVENTS = "Repository name / master"


class Bitbucket2HookTests(WebhookTestCase):
    CHANNEL_NAME = "bitbucket2"
    URL_TEMPLATE = "/api/v1/external/bitbucket2?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "bitbucket2"

    def test_bitbucket2_on_push_event(self) -> None:
        commit_info = "* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"
        expected_message = f"Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n{commit_info}"
        self.check_webhook("push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers(self) -> None:
        commit_info = "* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n"
        expected_message = f"""Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 3 commits to branch master. Commits by Ben (2) and Tomasz (1).\n\n{commit_info * 2}* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook("push_multiple_committers", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_with_others(self) -> None:
        commit_info = "* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n"
        expected_message = f"""Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 10 commits to branch master. Commits by Tomasz (4), James (3), Brendon (2) and others (1).\n\n{commit_info * 9}* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook(
            "push_multiple_committers_with_others", TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket2_on_push_commits_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        commit_info = "* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n"
        expected_message = f"""Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 3 commits to branch master. Commits by Ben (2) and Tomasz (1).\n\n{commit_info * 2}* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook("push_multiple_committers", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_multiple_committers_with_others_filtered_by_branches(
        self,
    ) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        commit_info = "* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))\n"
        expected_message = f"""Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 10 commits to branch master. Commits by Tomasz (4), James (3), Brendon (2) and others (1).\n\n{commit_info * 9}* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"""
        self.check_webhook(
            "push_multiple_committers_with_others", TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket2_on_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        commit_info = "* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))"
        expected_message = f"Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n{commit_info}"
        self.check_webhook("push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_event(self) -> None:
        commit_info = "* a ([6f161a7bced](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0))\n"
        expected_message = f"Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) 5 commits to branch master.\n\n{(commit_info * 5)}[and more commit(s)]"
        self.check_webhook("push_commits_above_limit", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_push_commits_above_limit_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        commit_info = "* a ([6f161a7bced](https://bitbucket.org/kolaszek/repository-name/commits/6f161a7bced94430ac8947d87dbf45c6deee3fb0))\n"
        expected_message = f"Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branches/compare/6f161a7bced94430ac8947d87dbf45c6deee3fb0..1221f2fda6f1e3654b09f1f3a08390e4cb25bb48) 5 commits to branch master.\n\n{(commit_info * 5)}[and more commit(s)]"

        self.check_webhook("push_commits_above_limit", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event(self) -> None:
        expected_message = "Tomasz [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12."
        self.check_webhook("force_push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_force_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        expected_message = "Tomasz [force pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) to branch master. Head is now 25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12."
        self.check_webhook("force_push", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_remove_branch_event(self) -> None:
        expected_message = "Tomasz deleted branch master."
        self.check_webhook("remove_branch", TOPIC_BRANCH_EVENTS, expected_message)

    def test_bitbucket2_on_fork_event(self) -> None:
        expected_message = "Tomasz forked the repository into [kolaszek/repository-name2](https://bitbucket.org/kolaszek/repository-name2)."
        self.check_webhook("fork", TOPIC, expected_message)

    def test_bitbucket2_on_commit_comment_created_event(self) -> None:
        expected_message = "Tomasz [commented](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74#comment-3354963) on [32c4ea19aa3](https://bitbucket.org/kolaszek/repository-name/commits/32c4ea19aa3af10acd08e419e2c354941a365d74):\n~~~ quote\nNice fix!\n~~~"
        self.check_webhook("commit_comment_created", TOPIC, expected_message)

    def test_bitbucket2_on_commit_status_changed_event(self) -> None:
        expected_message = "[System mybuildtool](https://my-build-tool.com/builds/MY-PROJECT/BUILD-777) changed status of [9fec847784a](https://bitbucket.org/kolaszek/repository-name/commits/9fec847784abb10b2fa567ee63b85bd238955d0e) to SUCCESSFUL."
        self.check_webhook("commit_status_changed", TOPIC, expected_message)

    def test_bitbucket2_on_issue_created_event(self) -> None:
        expected_message = "Tomasz created [issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug) (assigned to Tomasz):\n\n~~~ quote\nSuch a bug\n~~~"
        self.check_webhook("issue_created", TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Tomasz created [issue #1 Bug](https://bitbucket.org/kolaszek/repository-name/issues/2/bug) (assigned to Tomasz):\n\n~~~ quote\nSuch a bug\n~~~"
        self.check_webhook("issue_created", expected_topic_name, expected_message)

    def test_bitbucket2_on_issue_updated_event(self) -> None:
        expected_message = "Tomasz updated [issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)."
        self.check_webhook("issue_updated", TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_event(self) -> None:
        expected_message = "Tomasz [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [issue #1](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)."
        self.check_webhook("issue_commented", TOPIC_ISSUE_EVENTS, expected_message)

    def test_bitbucket2_on_issue_commented_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Tomasz [commented](https://bitbucket.org/kolaszek/repository-name/issues/2#comment-28973596) on [issue #1 Bug](https://bitbucket.org/kolaszek/repository-name/issues/2/bug)."
        self.check_webhook("issue_commented", expected_topic_name, expected_message)

    def test_bitbucket2_on_pull_request_created_event(self) -> None:
        expected_message = "Tomasz created [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) from `new-branch` to `master` (assigned to Tomasz Kolek):\n\n~~~ quote\ndescription\n~~~"
        self.check_webhook(
            "pull_request_created_or_updated",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:created",
        )

    def test_bitbucket2_on_pull_request_created_without_reviewer_username_event(self) -> None:
        expected_message = "Tomasz created [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) from `new-branch` to `master` (assigned to Tomasz Kolek):\n\n~~~ quote\ndescription\n~~~"
        self.check_webhook(
            "pull_request_created_or_updated_without_username",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:created",
        )

    def test_bitbucket2_on_pull_request_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Tomasz created [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) from `new-branch` to `master` (assigned to Tomasz Kolek):\n\n~~~ quote\ndescription\n~~~"
        self.check_webhook(
            "pull_request_created_or_updated",
            expected_topic_name,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:created",
        )

    def test_bitbucket2_on_pull_request_updated_event(self) -> None:
        expected_message = "Tomasz updated [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) (assigned to Tomasz Kolek):\n\n~~~ quote\ndescription\n~~~"
        self.check_webhook(
            "pull_request_created_or_updated",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:updated",
        )

    def test_bitbucket2_on_pull_request_approved_event(self) -> None:
        expected_message = "Tomasz approved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        self.check_webhook(
            "pull_request_approved_or_unapproved",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:approved",
        )

    def test_bitbucket2_on_pull_request_approved_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Tomasz approved [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        self.check_webhook(
            "pull_request_approved_or_unapproved",
            expected_topic_name,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:approved",
        )

    def test_bitbucket2_on_pull_request_unapproved_event(self) -> None:
        expected_message = "Tomasz unapproved [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        self.check_webhook(
            "pull_request_approved_or_unapproved",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:unapproved",
        )

    def test_bitbucket2_on_pull_request_declined_event(self) -> None:
        expected_message = "Tomasz rejected [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1)."
        self.check_webhook(
            "pull_request_fulfilled_or_rejected",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:rejected",
        )

    def test_bitbucket2_on_pull_request_fulfilled_event(self) -> None:
        expected_message = "Tomasz merged [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/1) from `new-branch` to `master`."
        self.check_webhook(
            "pull_request_fulfilled_or_rejected",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:fulfilled",
        )

    def test_bitbucket2_on_pull_request_comment_created_event(self) -> None:
        expected_message = "Tomasz [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        self.check_webhook(
            "pull_request_comment_action",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:comment_created",
        )

    def test_bitbucket2_on_pull_request_comment_created_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Tomasz [commented](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        self.check_webhook(
            "pull_request_comment_action",
            expected_topic_name,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:comment_created",
        )

    def test_bitbucket2_on_pull_request_comment_updated_event(self) -> None:
        expected_message = "Tomasz updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        self.check_webhook(
            "pull_request_comment_action",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:comment_updated",
        )

    def test_bitbucket2_on_pull_request_comment_updated_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = "Tomasz updated a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1 new commit](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        self.check_webhook(
            "pull_request_comment_action",
            expected_topic_name,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:comment_updated",
        )

    def test_bitbucket2_on_pull_request_comment_deleted_event(self) -> None:
        expected_message = "Tomasz deleted a [comment](https://bitbucket.org/kolaszek/repository-name/pull-requests/3/_/diff#comment-20576503) on [PR #1](https://bitbucket.org/kolaszek/repository-name/pull-requests/3):\n\n~~~ quote\nComment1\n~~~"
        self.check_webhook(
            "pull_request_comment_action",
            TOPIC_PR_EVENTS,
            expected_message,
            HTTP_X_EVENT_KEY="pullrequest:comment_deleted",
        )

    def test_bitbucket2_on_repo_updated_event(self) -> None:
        expected_message = "eeshangarg changed the website of the **new-name** repo to **http://zulipchat.com**.\neeshangarg changed the name of the **new-name** repo from **test-repo** to **new-name**.\neeshangarg changed the language of the **new-name** repo to **python**.\neeshangarg changed the full name of the **new-name** repo from **webhooktest/test-repo** to **webhooktest/new-name**.\neeshangarg changed the description of the **new-name** repo to **Random description.**"
        expected_topic_name = "new-name"
        self.check_webhook(
            "repo_updated", expected_topic_name, expected_message, HTTP_X_EVENT_KEY="repo:updated"
        )

    def test_bitbucket2_on_push_one_tag_event(self) -> None:
        expected_message = (
            "Tomasz pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)."
        )
        self.check_webhook(
            "push_one_tag", TOPIC, expected_message, HTTP_X_EVENT_KEY="pullrequest:push"
        )

    def test_bitbucket2_on_push_remove_tag_event(self) -> None:
        expected_message = (
            "Tomasz removed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)."
        )
        self.check_webhook(
            "push_remove_tag", TOPIC, expected_message, HTTP_X_EVENT_KEY="pullrequest:push"
        )

    def test_bitbucket2_on_push_more_than_one_tag_event(self) -> None:
        expected_message = "Tomasz pushed tag [{name}](https://bitbucket.org/kolaszek/repository-name/commits/tag/{name})."

        self.subscribe(self.test_user, self.CHANNEL_NAME)
        payload = self.get_body("push_more_than_one_tag")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
            HTTP_X_EVENT_KEY="pullrequest:push",
        )

        msg = self.get_second_to_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC,
            content=expected_message.format(name="a"),
        )

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC,
            content=expected_message.format(name="b"),
        )

    def test_bitbucket2_on_more_than_one_push_event(self) -> None:
        self.subscribe(self.test_user, self.CHANNEL_NAME)
        payload = self.get_body("more_than_one_push_event")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
            HTTP_X_EVENT_KEY="pullrequest:push",
        )

        msg = self.get_second_to_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC_BRANCH_EVENTS,
            content="Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))",
        )

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC,
            content="Tomasz pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a).",
        )

    def test_bitbucket2_on_more_than_one_push_event_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")

        self.subscribe(self.test_user, self.CHANNEL_NAME)
        payload = self.get_body("more_than_one_push_event")

        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            payload,
            content_type="application/json",
            HTTP_X_EVENT_KEY="pullrequest:push",
        )

        msg = self.get_second_to_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC_BRANCH_EVENTS,
            content="Tomasz [pushed](https://bitbucket.org/kolaszek/repository-name/branch/master) 1 commit to branch master.\n\n* first commit ([84b96adc644](https://bitbucket.org/kolaszek/repository-name/commits/84b96adc644a30fd6465b3d196369d880762afed))",
        )

        msg = self.get_last_message()
        self.assert_channel_message(
            message=msg,
            channel_name=self.CHANNEL_NAME,
            topic_name=TOPIC,
            content="Tomasz pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a).",
        )

    def test_bitbucket2_on_more_than_one_push_event_filtered_by_branches_ignore(self) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        expected_message = (
            "Tomasz pushed tag [a](https://bitbucket.org/kolaszek/repository-name/commits/tag/a)."
        )
        self.check_webhook(
            "more_than_one_push_event", TOPIC, expected_message, HTTP_X_EVENT_KEY="pullrequest:push"
        )

    @patch("zerver.webhooks.bitbucket2.view.check_send_webhook_message")
    def test_bitbucket2_on_push_event_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.bitbucket2.view.check_send_webhook_message")
    def test_bitbucket2_on_push_commits_above_limit_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push_commits_above_limit")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.bitbucket2.view.check_send_webhook_message")
    def test_bitbucket2_on_force_push_event_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("force_push")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.bitbucket2.view.check_send_webhook_message")
    def test_bitbucket2_on_push_multiple_committers_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push_multiple_committers")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.bitbucket2.view.check_send_webhook_message")
    def test_bitbucket2_on_push_multiple_committers_with_others_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push_multiple_committers_with_others")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.bitbucket2.view.check_send_webhook_message")
    def test_bitbucket2_on_push_without_changes_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        payload = self.get_body("push_without_changes")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_get_user_info(self) -> None:
        request = HostRequestMock()
        request.content_type = "application/json"
        request.user = self.test_user
        RequestNotes.get_notes(request).client = get_client("test")

        self.assertEqual(get_user_info(request, wrap_wild_value("request", {})), "Unknown user")

        dct = dict(
            nickname="alice",
            noisy_field="whatever",
            display_name="Alice Smith",
        )

        self.assertEqual(get_user_info(request, wrap_wild_value("request", dct)), "Alice Smith")
        del dct["display_name"]

        self.assertEqual(get_user_info(request, wrap_wild_value("request", dct)), "alice")
        del dct["nickname"]

        self.assertEqual(get_user_info(request, wrap_wild_value("request", dct)), "Unknown user")
