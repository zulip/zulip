from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

TOPIC = "Repository name"
TOPIC_BRANCH_EVENTS = "Repository name / master"


class BitbucketHookTests(WebhookTestCase):
    CHANNEL_NAME = "bitbucket"
    URL_TEMPLATE = "/api/v1/external/bitbucket?stream={stream}"
    WEBHOOK_DIR_NAME = "bitbucket"

    def test_bitbucket_on_push_event(self) -> None:
        fixture_name = "push"
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        commit_info = "* c ([25f93d22b71](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))"
        expected_message = f"kolaszek pushed 1 commit to branch master.\n\n{commit_info}"
        self.api_channel_message(
            self.test_user, fixture_name, TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket_on_push_event_without_user_info(self) -> None:
        fixture_name = "push_without_user_info"
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        commit_info = "* c ([25f93d22b71](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))"
        expected_message = (
            f"Someone pushed 1 commit to branch master. Commits by eeshangarg (1).\n\n{commit_info}"
        )
        self.api_channel_message(
            self.test_user, fixture_name, TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket_on_push_event_filtered_by_branches(self) -> None:
        fixture_name = "push"
        self.url = self.build_webhook_url(
            payload=self.get_body(fixture_name), branches="master,development"
        )
        commit_info = "* c ([25f93d22b71](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))"
        expected_message = f"kolaszek pushed 1 commit to branch master.\n\n{commit_info}"
        self.api_channel_message(
            self.test_user, fixture_name, TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket_on_push_commits_above_limit_event(self) -> None:
        fixture_name = "push_commits_above_limit"
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        commit_info = "* c ([25f93d22b71](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))\n"
        expected_message = f"kolaszek pushed 50 commits to branch master.\n\n{commit_info * 20}[and 30 more commit(s)]"
        self.api_channel_message(
            self.test_user, fixture_name, TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket_on_push_commits_above_limit_event_filtered_by_branches(self) -> None:
        fixture_name = "push_commits_above_limit"
        self.url = self.build_webhook_url(
            payload=self.get_body(fixture_name), branches="master,development"
        )
        commit_info = "* c ([25f93d22b71](https://bitbucket.org/kolaszek/repository-name/commits/25f93d22b719e2d678a7ad5ee0ef0d1fcdf39c12))\n"
        expected_message = f"kolaszek pushed 50 commits to branch master.\n\n{commit_info * 20}[and 30 more commit(s)]"
        self.api_channel_message(
            self.test_user, fixture_name, TOPIC_BRANCH_EVENTS, expected_message
        )

    def test_bitbucket_on_force_push_event(self) -> None:
        fixture_name = "force_push"
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        expected_message = (
            "kolaszek [force pushed](https://bitbucket.org/kolaszek/repository-name)."
        )
        self.api_channel_message(self.test_user, fixture_name, TOPIC, expected_message)

    def test_bitbucket_on_force_push_event_without_user_info(self) -> None:
        fixture_name = "force_push_without_user_info"
        self.url = self.build_webhook_url(payload=self.get_body(fixture_name))
        expected_message = (
            "Someone [force pushed](https://bitbucket.org/kolaszek/repository-name/)."
        )
        self.api_channel_message(self.test_user, fixture_name, TOPIC, expected_message)

    @patch("zerver.webhooks.bitbucket.view.check_send_webhook_message")
    def test_bitbucket_on_push_event_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        fixture_name = "push"
        payload = self.get_body(fixture_name)
        self.url = self.build_webhook_url(payload=payload, branches="changes,development")
        result = self.api_post(self.test_user, self.url, payload, content_type="application/json,")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.bitbucket.view.check_send_webhook_message")
    def test_bitbucket_push_commits_above_limit_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        fixture_name = "push_commits_above_limit"
        payload = self.get_body(fixture_name)
        self.url = self.build_webhook_url(payload=payload, branches="changes,development")
        result = self.api_post(self.test_user, self.url, payload, content_type="application/json,")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)
