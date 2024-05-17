from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT


class AzuredevopsHookTests(WebhookTestCase):
    CHANNEL_NAME = "azure-devops"
    URL_TEMPLATE = "/api/v1/external/azuredevops?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "azuredevops"

    def test_push_event_message(self) -> None:
        expected_topic_name = "test-zulip / main"
        expected_message = "Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GC51515957669f93c543df09f8f3e7f47c3613c879&targetVersion=GCb0ce2f2009c3c87dbefadf61d7eb2c0697a6f369&_a=files) 1 commit to branch main.\n\n* Modify readme ([b0ce2f2009c](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/b0ce2f2009c3c87dbefadf61d7eb2c0697a6f369))"
        self.check_webhook("code_push", expected_topic_name, expected_message)

    def test_push_event_message_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="main,dev")
        expected_topic_name = "test-zulip / main"
        expected_message = "Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GC51515957669f93c543df09f8f3e7f47c3613c879&targetVersion=GCb0ce2f2009c3c87dbefadf61d7eb2c0697a6f369&_a=files) 1 commit to branch main.\n\n* Modify readme ([b0ce2f2009c](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/b0ce2f2009c3c87dbefadf61d7eb2c0697a6f369))"
        self.check_webhook("code_push", expected_topic_name, expected_message)

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_push_event_message_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="development")
        payload = self.get_body("code_push")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_push_local_branch_without_commits(self) -> None:
        expected_topic_name = "test-zulip / dev"
        expected_message = "Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GC0000000000000000000000000000000000000000&targetVersion=GC0929a3404b39f6e39076a640779b2c1c961e19b5&_a=files) the branch dev."
        self.check_webhook(
            "code_push__local_branch_without_commits", expected_topic_name, expected_message
        )

    def test_push_multiple_committers(self) -> None:
        expected_topic_name = "test-zulip / main"
        expected_message = "Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GCcc21b940719cc372b364d932eb39e528b0ec2a91&targetVersion=GC0929a3404b39f6e39076a640779b2c1c961e19b5&_a=files) 2 commits to branch main. Commits by Itachi Sensei (1) and Yuro Itaki (1).\n\n* Add reply ([0929a3404b3](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/0929a3404b39f6e39076a640779b2c1c961e19b5))\n* Add how are you ([819ce8de51b](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/819ce8de51bedfc250c202edcaee0ce8dc70bf3b))"
        self.check_webhook("code_push__multiple_committers", expected_topic_name, expected_message)

    def test_push_multiple_committers_with_others(self) -> None:
        expected_topic_name = "test-zulip / main"
        commits_info = "* Add how are you ([819ce8de51b](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/819ce8de51bedfc250c202edcaee0ce8dc70bf3b))\n"
        expected_message = f"Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GCcc21b940719cc372b364d932eb39e528b0ec2a91&targetVersion=GC0929a3404b39f6e39076a640779b2c1c961e19b5&_a=files) 6 commits to branch main. Commits by Itachi Sensei (2), Yuro Itaki (2), Jonas Nielsen (1) and others (1).\n\n* Add reply ([0929a3404b3](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/0929a3404b39f6e39076a640779b2c1c961e19b5))\n{commits_info * 4}* Add reply ([0929a3404b3](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/0929a3404b39f6e39076a640779b2c1c961e19b5))"
        self.check_webhook(
            "code_push__multiple_committers_with_others", expected_topic_name, expected_message
        )

    def test_push_commits_more_than_limit(self) -> None:
        expected_topic_name = "test-zulip / main"
        commits_info = "* Modify readme ([b0ce2f2009c](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/commit/b0ce2f2009c3c87dbefadf61d7eb2c0697a6f369))\n"
        expected_message = f"Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GC51515957669f93c543df09f8f3e7f47c3613c879&targetVersion=GCb0ce2f2009c3c87dbefadf61d7eb2c0697a6f369&_a=files) 50 commits to branch main.\n\n{commits_info * COMMITS_LIMIT}[and {50 - COMMITS_LIMIT} more commit(s)]"
        self.check_webhook(
            "code_push__commits_more_than_limit", expected_topic_name, expected_message
        )

    def test_push_remove_branch(self) -> None:
        expected_topic_name = "test-zulip / dev"
        expected_message = "Yuro Itaki [pushed](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/branchCompare?baseVersion=GC0929a3404b39f6e39076a640779b2c1c961e19b5&targetVersion=GC0000000000000000000000000000000000000000&_a=files) the branch dev."
        self.check_webhook("code_push__remove_branch", expected_topic_name, expected_message)

    def test_pull_request_opened(self) -> None:
        expected_topic_name = "test-zulip / PR #1 Add PR request"
        expected_message = "Yuro Itaki created [PR #1 Add PR request](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/pullrequest/1) from `dev` to `main`:\n\n~~~ quote\nAdd PR request\n~~~"
        self.check_webhook("code_pull_request__opened", expected_topic_name, expected_message)

    def test_pull_request_opened_without_description(self) -> None:
        expected_topic_name = "test-zulip / PR #2 Raised 2nd PR!"
        expected_message = "Yuro Itaki created [PR #2 Raised 2nd PR!](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/pullrequest/2) from `stg` to `main`."
        self.check_webhook(
            "code_pull_request__opened_without_description", expected_topic_name, expected_message
        )

    def test_pull_request_merged(self) -> None:
        expected_topic_name = "test-zulip / PR #1 Add PR request"
        expected_message = "Yuro Itaki merged [PR #1 Add PR request](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/pullrequest/1) from `dev` to `main`."
        self.check_webhook("code_pull_request__merged", expected_topic_name, expected_message)

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_pull_request_merge_attempted_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("code_pull_request__merge_attempted")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_pull_request_updated(self) -> None:
        expected_topic_name = "test-zulip / PR #2 Raised 2nd PR!"
        expected_message = "Yuro Itaki updated [PR #2 Raised 2nd PR!](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/pullrequest/2)\n\n~~~ quote\nYuro Itaki updated the source branch of [pull request 2](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/pullrequest/2) (Raised 2nd PR!) in [test-zulip](https://dev.azure.com/ttchong/test-zulip/_git/test-zulip/)\r\nRaised 2nd PR!\r\n\n~~~"
        self.check_webhook("code_pull_request__updated", expected_topic_name, expected_message)
