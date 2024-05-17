from zerver.lib.test_classes import WebhookTestCase


class CircleCiHookTests(WebhookTestCase):
    CHANNEL_NAME = "circleci"
    URL_TEMPLATE = "/api/v1/external/circleci?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "circleci"

    def test_ping(self) -> None:
        expected_topic_name = "Test event"
        expected_message = "Webhook 'Testing' test event successful."
        self.check_webhook("ping", expected_topic_name, expected_message)

    def test_bitbucket_job_completed(self) -> None:
        expected_topic_name = "circleci-webhook-testing"
        expected_message = """
Job `build-and-test` within Pipeline #4 has succeeded.

Triggered on [`8ab595d2de9: app.py edited online with Bitbucket`](https://bitbucket.org/hariprashant1/circleci-webhook-testing/commits/8ab595d2de95767993472837df2cb7884519a92b) on branch `master` by Hari Prashant Bhimaraju.
""".strip()
        self.check_webhook("bitbucket_job_completed", expected_topic_name, expected_message)

    def test_bitbucket_manual_workflow_completed(self) -> None:
        expected_topic_name = "circleci-webhook-testing"
        expected_message = """
Workflow [`sample`](https://app.circleci.com/pipelines/bitbucket/hariprashant1/circleci-webhook-testing/2/workflows/baa45986-84db-47a0-bc6c-89e9fe751bc9) within Pipeline #2 has succeeded.

Triggered on `master`'s HEAD on [cab5eacb4cc](https://bitbucket.org/hariprashant1/circleci-webhook-testing/commits/cab5eacb4ccee2710529894425341fa20a48fe6a).
""".strip()
        self.check_webhook(
            "bitbucket_manual_workflow_completed", expected_topic_name, expected_message
        )

    def test_bitbucket_workflow_completed(self) -> None:
        expected_topic_name = "circleci-webhook-testing"
        expected_message = """
Workflow [`sample`](https://app.circleci.com/pipelines/bitbucket/hariprashant1/circleci-webhook-testing/4/workflows/fd29ef0c-3e39-4c8f-b1d5-d8be1bab8165) within Pipeline #4 has succeeded.

Triggered on [`8ab595d2de9: app.py edited online with Bitbucket`](https://bitbucket.org/hariprashant1/circleci-webhook-testing/commits/8ab595d2de95767993472837df2cb7884519a92b) on branch `master` by Hari Prashant Bhimaraju.
""".strip()
        self.check_webhook("bitbucket_workflow_completed", expected_topic_name, expected_message)

    def test_github_job_completed(self) -> None:
        expected_topic_name = "circleci-webhook-test"
        expected_message = """
Job `build-and-test` within Pipeline #4 has succeeded.

Triggered on [`a5e30a90822: .circleci: Update Webhook URL.`](https://github.com/zulip-testing/circleci-webhook-test/commit/a5e30a908224e46626a796d058289475f6d387b5) on branch `main` by Hari Prashant Bhimaraju.
""".strip()
        self.check_webhook("github_job_completed", expected_topic_name, expected_message)

    def test_github_tag_workflow_completed(self) -> None:
        expected_topic_name = "circleci-webhook-test"
        expected_message = """
Workflow [`sample`](https://app.circleci.com/pipelines/github/prah23/circleci-webhook-test/20/workflows/045c6271-78e2-4802-8a62-f4fa6d25d0c9) within Pipeline #20 has succeeded.

Triggered on the latest tag on [0e6e66c14e6](https://github.com/prah23/circleci-webhook-test/commit/0e6e66c14e61fbcd95db716b0f30d67dbcce7814).
""".strip()
        self.check_webhook("github_tag_workflow_completed", expected_topic_name, expected_message)

    def test_github_workflow_completed(self) -> None:
        expected_topic_name = "circleci-webhook-test"
        expected_message = """
Workflow [`sample`](https://app.circleci.com/pipelines/github/zulip-testing/circleci-webhook-test/4/workflows/7381218b-d04c-4aa3-b8b8-8c00a9319d1f) within Pipeline #4 has succeeded.

Triggered on [`a5e30a90822: .circleci: Update Webhook URL.`](https://github.com/zulip-testing/circleci-webhook-test/commit/a5e30a908224e46626a796d058289475f6d387b5) on branch `main` by Hari Prashant Bhimaraju.
""".strip()
        self.check_webhook("github_workflow_completed", expected_topic_name, expected_message)

    def test_gitlab_job_completed(self) -> None:
        expected_topic_name = "circleci-webhook-test"
        expected_message = """
Job `build-and-test` within Pipeline #3 has succeeded.

Triggered on [`c31f86994c5: app: Enhance message within hello().`](https://gitlab.com/zulip-testing/circleci-webhook-test/-/commit/c31f86994c54672f97b5bd5e544315b7bd40e4c1) on branch `main` by Hari Prashant Bhimaraju.
""".strip()
        self.check_webhook("gitlab_job_completed", expected_topic_name, expected_message)

    def test_gitlab_workflow_completed(self) -> None:
        expected_topic_name = "circleci-webhook-test"
        expected_message = """
Workflow [`sample`](https://app.circleci.com/pipelines/circleci/89xcrx7UvWQfzcUPAEmu5Q/63AY3yf3XeUQojmQcGZTtB/3/workflows/b23ceb64-127a-4075-a27c-d204a7a0a3b3) within Pipeline #3 has succeeded.

Triggered on [`c31f86994c5: app: Enhance message within hello().`](https://gitlab.com/zulip-testing/circleci-webhook-test/-/commit/c31f86994c54672f97b5bd5e544315b7bd40e4c1) on branch `main` by Hari Prashant Bhimaraju.
""".strip()
        self.check_webhook("gitlab_workflow_completed", expected_topic_name, expected_message)
