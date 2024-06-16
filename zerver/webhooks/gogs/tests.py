from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.git import COMMITS_LIMIT


class GogsHookTests(WebhookTestCase):
    CHANNEL_NAME = "commits"
    URL_TEMPLATE = "/api/v1/external/gogs?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "gogs"

    def test_push(self) -> None:
        expected_topic_name = "try-git / master"
        expected_message = """john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 1 commit to branch master. Commits by John (1).

* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))"""
        self.check_webhook("push", expected_topic_name, expected_message)

    def test_push_multiple_committers(self) -> None:
        commit_info = "* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n"
        expected_topic_name = "try-git / master"
        expected_message = f"""john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 2 commits to branch master. Commits by Benjamin (1) and John (1).\n\n{commit_info}* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))"""
        self.check_webhook(
            "push__commits_multiple_committers", expected_topic_name, expected_message
        )

    def test_push_multiple_committers_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        commit_info = "* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n"
        expected_topic_name = "try-git / master"
        expected_message = f"""john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 2 commits to branch master. Commits by Benjamin (1) and John (1).\n\n{commit_info}* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))"""
        self.check_webhook(
            "push__commits_multiple_committers", expected_topic_name, expected_message
        )

    def test_push_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        expected_topic_name = "try-git / master"
        expected_message = """john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 1 commit to branch master. Commits by John (1).

* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))"""
        self.check_webhook("push", expected_topic_name, expected_message)

    def test_push_commits_more_than_limits(self) -> None:
        expected_topic_name = "try-git / master"
        commits_info = "* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n"
        expected_message = f"john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 30 commits to branch master. Commits by John (30).\n\n{commits_info * COMMITS_LIMIT}[and {30 - COMMITS_LIMIT} more commit(s)]"
        self.check_webhook("push__commits_more_than_limits", expected_topic_name, expected_message)

    def test_push_commits_more_than_limits_filtered_by_branches(self) -> None:
        self.url = self.build_webhook_url(branches="master,development")
        expected_topic_name = "try-git / master"
        commits_info = "* Webhook Test ([d8fce16c72a](http://localhost:3000/john/try-git/commit/d8fce16c72a2ff56a5afc8a08645a6ce45491794))\n"
        expected_message = f"john [pushed](http://localhost:3000/john/try-git/compare/479e6b772b7fba19412457483f50b201286d0103...d8fce16c72a2ff56a5afc8a08645a6ce45491794) 30 commits to branch master. Commits by John (30).\n\n{commits_info * COMMITS_LIMIT}[and {30 - COMMITS_LIMIT} more commit(s)]"
        self.check_webhook("push__commits_more_than_limits", expected_topic_name, expected_message)

    def test_new_branch(self) -> None:
        expected_topic_name = "try-git / my_feature"
        expected_message = (
            "john created [my_feature](http://localhost:3000/john/try-git/src/my_feature) branch."
        )
        self.check_webhook("create__branch", expected_topic_name, expected_message)

    def test_pull_request_opened(self) -> None:
        expected_topic_name = "try-git / PR #1 Title Text for Pull Request"
        expected_message = """john opened [PR #1](http://localhost:3000/john/try-git/pulls/1) from `feature` to `master`."""
        self.check_webhook("pull_request__opened", expected_topic_name, expected_message)

    def test_pull_request_opened_with_custom_topic_in_url(self) -> None:
        self.url = self.build_webhook_url(topic="notifications")
        expected_topic_name = "notifications"
        expected_message = """john opened [PR #1 Title Text for Pull Request](http://localhost:3000/john/try-git/pulls/1) from `feature` to `master`."""
        self.check_webhook("pull_request__opened", expected_topic_name, expected_message)

    def test_pull_request_closed(self) -> None:
        expected_topic_name = "try-git / PR #1 Title Text for Pull Request"
        expected_message = """john closed [PR #1](http://localhost:3000/john/try-git/pulls/1) from `feature` to `master`."""
        self.check_webhook("pull_request__closed", expected_topic_name, expected_message)

    def test_pull_request_merged(self) -> None:
        expected_topic_name = "try-git / PR #2 Title Text for Pull Request"
        expected_message = """john merged [PR #2](http://localhost:3000/john/try-git/pulls/2) from `feature` to `master`."""
        self.check_webhook("pull_request__merged", expected_topic_name, expected_message)

    def test_pull_request_reopened(self) -> None:
        expected_topic_name = "test / PR #1349 reopened"
        expected_message = """kostekIV reopened [PR #2](https://try.gogs.io/kostekIV/test/pulls/2) from `c` to `master`."""
        self.check_webhook("pull_request__reopened", expected_topic_name, expected_message)

    def test_pull_request_edited(self) -> None:
        expected_topic_name = "test / PR #1349 Test"
        expected_message = """kostekIV edited [PR #2](https://try.gogs.io/kostekIV/test/pulls/2)."""
        self.check_webhook("pull_request__edited", expected_topic_name, expected_message)

    def test_pull_request_assigned(self) -> None:
        expected_topic_name = "test / PR #1349 Test"
        expected_message = """kostekIV assigned [PR #2](https://try.gogs.io/kostekIV/test/pulls/2) from `c` to `master`."""
        self.check_webhook("pull_request__assigned", expected_topic_name, expected_message)

    def test_pull_request_synchronized(self) -> None:
        expected_topic_name = "test / PR #1349 Test"
        expected_message = """kostekIV synchronized [PR #2](https://try.gogs.io/kostekIV/test/pulls/2) from `c` to `master`."""
        self.check_webhook("pull_request__synchronized", expected_topic_name, expected_message)

    def test_issues_opened(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV opened [issue #3](https://try.gogs.io/kostekIV/test/issues/3):\n\n~~~ quote\nTest\n~~~"""
        self.check_webhook("issues__opened", expected_topic_name, expected_message)

    def test_issues_reopened(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV reopened [issue #3](https://try.gogs.io/kostekIV/test/issues/3):\n\n~~~ quote\nTest\n~~~"""
        self.check_webhook("issues__reopened", expected_topic_name, expected_message)

    def test_issues_edited(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV edited [issue #3](https://try.gogs.io/kostekIV/test/issues/3):\n\n~~~ quote\nTest edit\n~~~"""
        self.check_webhook("issues__edited", expected_topic_name, expected_message)

    def test_issues_assignee(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV assigned [issue #3](https://try.gogs.io/kostekIV/test/issues/3) (assigned to kostekIV):\n\n~~~ quote\nTest\n~~~"""
        self.check_webhook("issues__assigned", expected_topic_name, expected_message)

    def test_issues_closed(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV closed [issue #3](https://try.gogs.io/kostekIV/test/issues/3):\n\n~~~ quote\nClosed #3\n~~~"""
        self.check_webhook("issues__closed", expected_topic_name, expected_message)

    def test_issue_comment_new(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV [commented](https://try.gogs.io/kostekIV/test/issues/3#issuecomment-3635) on [issue #3](https://try.gogs.io/kostekIV/test/issues/3):\n\n~~~ quote\nTest comment\n~~~"""
        self.check_webhook("issue_comment__new", expected_topic_name, expected_message)

    def test_issue_comment_edited(self) -> None:
        expected_topic_name = "test / issue #3 New test issue"
        expected_message = """kostekIV edited a [comment](https://try.gogs.io/kostekIV/test/issues/3#issuecomment-3634) on [issue #3](https://try.gogs.io/kostekIV/test/issues/3):\n\n~~~ quote\nedit comment\n~~~"""
        self.check_webhook("issue_comment__edited", expected_topic_name, expected_message)

    def test_release_published(self) -> None:
        expected_topic_name = "zulip_test / v1.4 Title"
        expected_message = """cestrell published release [Title](https://try.gogs.io/cestrell/zulip_test) for tag v1.4."""
        self.check_webhook("release__published", expected_topic_name, expected_message)

    @patch("zerver.webhooks.gogs.view.check_send_webhook_message")
    def test_push_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push")
        result = self.client_post(
            self.url, payload, HTTP_X_GOGS_EVENT="push", content_type="application/json"
        )
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.gogs.view.check_send_webhook_message")
    def test_push_commits_more_than_limits_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push__commits_more_than_limits")
        result = self.client_post(
            self.url, payload, HTTP_X_GOGS_EVENT="push", content_type="application/json"
        )
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    @patch("zerver.webhooks.gogs.view.check_send_webhook_message")
    def test_push_multiple_committers_filtered_by_branches_ignore(
        self, check_send_webhook_message_mock: MagicMock
    ) -> None:
        self.url = self.build_webhook_url(branches="changes,development")
        payload = self.get_body("push__commits_multiple_committers")
        result = self.client_post(
            self.url, payload, HTTP_X_GOGS_EVENT="push", content_type="application/json"
        )
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)
