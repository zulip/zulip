from zerver.lib.test_classes import WebhookTestCase


class DBTHookTests(WebhookTestCase):
    CHANNEL_NAME = "DBT"
    URL_TEMPLATE = "/api/v1/external/dbt?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "dbt"

    def test_dbt_webhook_when_job_started(self) -> None:
        expected_message = """:yellow_circle: Daily Job (dbt build) deployment started in Production.
Job #123 was kicked off from the ui by test@test.com at <time:2023-01-31T19:28:07Z>."""
        self.check_webhook("job_run_started", "Example Project", expected_message)

    def test_dbt_webhook_when_job_completed(self) -> None:
        expected_message = """:green_circle: Daily Job (dbt build) deployment succeeded in Production at <time:2023-01-31T19:29:32Z>.
Job #123 was kicked off from the ui by test@test.com at <time:2023-01-31T19:28:07Z>."""
        self.check_webhook("job_run_completed", "Example Project", expected_message)

    def test_dbt_webhook_when_job_completed_but_errored(self) -> None:
        expected_message = """:cross_mark: Daily Job (dbt build) deployment completed with errors in Production at <time:2025-10-05T19:16:06Z>.
Job #123 was kicked off from the ui by test@test.com at <time:2025-10-05T19:15:56Z>."""
        self.check_webhook("job_run_completed_but_errored", "Example Project", expected_message)

    def test_dbt_webhook_when_job_errored(self) -> None:
        expected_message = """:cross_mark: Daily Job (dbt build) deployment failed in Production at <time:2023-01-31T21:15:20Z>.
Job #123 was kicked off from the ui by test@test.com at <time:2023-01-31T21:14:41Z>."""
        self.check_webhook("job_run_errored", "Example Project", expected_message)
