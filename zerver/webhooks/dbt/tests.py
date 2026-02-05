from zerver.lib.test_classes import WebhookTestCase


class DBTHookTests(WebhookTestCase):
    def test_dbt_webhook_when_job_started(self) -> None:
        expected_message = """:yellow_circle: Daily Job (dbt build) deployment started in **Production**.\n
Job #123 was kicked off from the UI by bwilliams@example.com at <time:2023-01-31T19:28:07Z>."""
        self.check_webhook("job_run_started", "Example Project", expected_message)

    def test_dbt_webhook_when_job_completed_success(self) -> None:
        expected_message = """:green_circle: Daily Job (dbt build) deployment succeeded in **Production**.\n
Job #123 was kicked off from the UI by bwilliams@example.com at <time:2023-01-31T19:28:07Z>."""
        self.check_webhook("job_run_completed_success", "Example Project", expected_message)

    def test_dbt_webhook_when_job_completed_errored(self) -> None:
        expected_message = """:cross_mark: Daily Job (dbt build) deployment completed with errors in **Production**.\n
Job #123 was kicked off from the UI by bwilliams@example.com at <time:2025-10-05T19:15:56Z>."""
        self.check_webhook("job_run_completed_errored", "Example Project", expected_message)

    def test_dbt_webhook_when_job_errored(self) -> None:
        expected_message = """:cross_mark: Daily Job (dbt build) deployment failed in **Production**.\n
Job #123 was kicked off from the UI by bwilliams@example.com at <time:2023-01-31T21:14:41Z>."""
        self.check_webhook("job_run_errored", "Example Project", expected_message)


class DBTHookWithAccessUrlTests(WebhookTestCase):
    URL_TEMPLATE = "/api/v1/external/dbt?&api_key={api_key}&stream={stream}&access_url=https%3A%2F%2Fexample.us1.dbt.com"

    def test_dbt_webhook_with_valid_access_url(self) -> None:
        expected_message = """:yellow_circle: Daily Job (dbt build) [deployment](https://example.us1.dbt.com/deploy/1/projects/167194/runs/12345) started in **Production**.\n
[Job #123](https://example.us1.dbt.com/deploy/1/projects/167194/jobs/123) was kicked off from the UI by bwilliams@example.com at <time:2023-01-31T19:28:07Z>."""
        self.check_webhook("job_run_started", "Example Project", expected_message)
