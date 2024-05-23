from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT


class RhodecodeHookTests(WebhookTestCase):
    CHANNEL_NAME = "rhodecode"
    URL_TEMPLATE = "/api/v1/external/rhodecode?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "rhodecode"

    def test_push_event_message(self) -> None:
        expected_topic_name = "u/yuroitaki/zulip-testing / master"
        expected_message = "yuroitaki pushed 1 commit to branch master. Commits by Yuro Itaki <yuroitaki@email.com> (1).\n\n* Modify README ([2b8c0ebf507](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/2b8c0ebf50710bc2e1cdb6a33071dd2435ad667c))"
        self.check_webhook("push", expected_topic_name, expected_message)

    def test_push_event_message_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,dev")
        expected_topic_name = "u/yuroitaki/zulip-testing / master"
        expected_message = "yuroitaki pushed 1 commit to branch master. Commits by Yuro Itaki <yuroitaki@email.com> (1).\n\n* Modify README ([2b8c0ebf507](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/2b8c0ebf50710bc2e1cdb6a33071dd2435ad667c))"
        self.check_webhook("push", expected_topic_name, expected_message)

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_push_event_message_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="development")
        payload = self.get_body("push")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_push_local_branch_without_commits(self) -> None:
        expected_topic_name = "u/yuroitaki/zulip-testing / dev"
        expected_message = "yuroitaki pushed the branch dev."
        self.check_webhook(
            "push__local_branch_without_commits", expected_topic_name, expected_message
        )

    def test_push_multiple_committers(self) -> None:
        expected_topic_name = "u/yuroitaki/zulip-testing / master"
        expected_message = "yuroitaki pushed 2 commits to branch master. Commits by Itachi Sensei <itachisensei@email.com> (1) and Yuro Itaki <yuroitaki@email.com> (1).\n\n* Add test.py ([b0d892e1cdd](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/b0d892e1cdd4236b1f74debca1772ea330ff5acd))\n* Modify test.py ([6dbae5f842f](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/6dbae5f842f80ccb05508a1de7aace9d0f327473))"
        self.check_webhook("push__multiple_committers", expected_topic_name, expected_message)

    def test_push_multiple_committers_with_others(self) -> None:
        expected_topic_name = "u/yuroitaki/zulip-testing / master"
        commits_info = "* Modify test.py ([6dbae5f842f](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/6dbae5f842f80ccb05508a1de7aace9d0f327473))\n"
        expected_message = f"yuroitaki pushed 6 commits to branch master. Commits by Itachi Sensei <itachisensei@email.com> (2), Yuro Itaki <yuroitaki@email.com> (2), Jonas Nielsen <jonasnielsen@email.com> (1) and others (1).\n\n* Add test.py ([b0d892e1cdd](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/b0d892e1cdd4236b1f74debca1772ea330ff5acd))\n{commits_info * 4}* Add test.py ([b0d892e1cdd](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/b0d892e1cdd4236b1f74debca1772ea330ff5acd))"
        self.check_webhook(
            "push__multiple_committers_with_others", expected_topic_name, expected_message
        )

    def test_push_commits_more_than_limit(self) -> None:
        expected_topic_name = "u/yuroitaki/zulip-testing / master"
        commits_info = "* Modify README ([2b8c0ebf507](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/2b8c0ebf50710bc2e1cdb6a33071dd2435ad667c))\n"
        expected_message = f"yuroitaki pushed 50 commits to branch master. Commits by Yuro Itaki <yuroitaki@email.com> (50).\n\n{commits_info * COMMITS_LIMIT}[and {50 - COMMITS_LIMIT} more commit(s)]"
        self.check_webhook("push__commits_more_than_limit", expected_topic_name, expected_message)

    def test_push_remove_branch(self) -> None:
        expected_topic_name = "u/yuroitaki/zulip-testing / dev"
        expected_message = "yuroitaki pushed 1 commit to branch dev. Commits by Yuro Itaki <yuroitaki@email.com> (1).\n\n* Deleted branch dev ([delete_bran](https://code.rhodecode.com/u/yuroitaki/zulip-testing/changeset/delete_branch=%3Edev))"
        self.check_webhook("push__remove_branch", expected_topic_name, expected_message)
