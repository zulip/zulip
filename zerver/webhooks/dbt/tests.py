from zerver.lib.test_classes import WebhookTestCase


class DBTHookTests(WebhookTestCase):
    CHANNEL_NAME = "DBT"
    URL_TEMPLATE = "/api/v1/external/dbt?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "dbt"

    def test_dbt_webhook_when_job_started(self) -> None:
        expected_message = """:yellow_circle: Daily Job (dbt build) deployment started in Production.
123 was kicked off from ui by test@test.com at <time:2023-01-31T19:28:07Z>."""
        self.check_webhook("job_run_started", "Example Project", expected_message)

    def test_dbt_webhook_when_job_completed(self) -> None:
        expected_message = """:green_circle: Daily Job (dbt build) deployment succeeded in Production.
123 was kicked off from ui by test@test.com at <time:2023-01-31T19:28:07Z>.
**Finished at**: <time:2023-01-31T19:29:32Z>"""
        self.check_webhook("job_run_completed", "Example Project", expected_message)

    def test_dbt_webhook_when_job_errored(self) -> None:
        expected_message = """:cross_mark: Daily Job (dbt build) deployment failed in Production.
123 was kicked off from ui by test@test.com at <time:2023-01-31T21:14:41Z>.
**Failed at**: <time:2023-01-31T21:15:20Z>"""
        self.check_webhook("job_run_errored", "Example Project", expected_message)
