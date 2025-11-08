from zerver.lib.test_classes import WebhookTestCase


class SonarqubeHookTests(WebhookTestCase):
    CHANNEL_NAME = "SonarQube"
    URL_TEMPLATE = "/api/v1/external/sonarqube?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "sonarqube"

    def test_analysis_success(self) -> None:
        expected_topic_name = "test-sonar / master"

        expected_message = """
Project [test-sonar](http://localhost:9000/dashboard?id=test-sonar) analysis of branch master resulted in success.
        """.strip()

        self.check_webhook(
            "success",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_analysis_error(self) -> None:
        expected_topic_name = "test-sonar / master"

        expected_message = """
Project [test-sonar](http://localhost:9000/dashboard?id=test-sonar) analysis of branch master resulted in error:
* coverage: **error** 0.0 should be greater than or equal to 80.
* duplicated lines density: **error** 89.39828080229226 should be less than or equal to 3.
        """.strip()

        self.check_webhook(
            "error",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_analysis_error_no_value(self) -> None:
        expected_topic_name = "test-sonar / master"

        expected_message = """
Project [test-sonar](http://localhost:9000/dashboard?id=test-sonar) analysis of branch master resulted in error:
* coverage: **error** 0.0 should be greater than or equal to 80.
* duplicated lines density: **error**.
        """.strip()

        self.check_webhook(
            "error_no_value",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_analysis_success_no_branch(self) -> None:
        expected_topic_name = "test-sonar"

        expected_message = """
Project [test-sonar](http://localhost:9000/dashboard?id=test-sonar) analysis resulted in success.
        """.strip()

        self.check_webhook(
            "success_no_branch",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_analysis_error_no_branch(self) -> None:
        expected_topic_name = "test-sonar"

        expected_message = """
Project [test-sonar](http://localhost:9000/dashboard?id=test-sonar) analysis resulted in error:
* coverage: **error** 0.0 should be greater than or equal to 80.
* duplicated lines density: **error** 89.39828080229226 should be less than or equal to 3.
        """.strip()

        self.check_webhook(
            "error_no_branch",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
