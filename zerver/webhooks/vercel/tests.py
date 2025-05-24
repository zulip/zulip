from zerver.lib.test_classes import WebhookTestCase


class VercelDeploymentHookTests(WebhookTestCase):
    CHANNEL_NAME = "vercel-notifications"
    URL_TEMPLATE = "/api/v1/external/vercel?&api_key={api_key}&stream={stream}&topic=sample-project"
    WEBHOOK_DIR_NAME = "vercel"

    def test_deployment_created(self) -> None:
        """
        Test Vercel webhook for created deployments.
        """
        expected_topic = "sample-project"
        expected_message = (
            "Production deployment by apoorvapendse **[created](https://vercel.com/apoorvapendses-projects/sample-project/Epq87qycdmXrX6hHMNodXFgFsBge)**."
            "\n>Update page.tsx ([d8282fc](https://github.com/apoorvapendse/sample-project/commit/d8282fc3c718d84ee3eb331a6e7a30f0790f3b69))"
        )
        self.check_webhook(
            "deployment_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_deployment_canceled(self) -> None:
        """
        Test Vercel webhook for canceled deployments.
        """
        expected_topic = "sample-project"
        expected_message = (
            "Deployment by apoorvapendse **[canceled](https://vercel.com/apoorvapendses-projects/sample-test-project/4eQ1GvKsPdb5EerGyL7C9313nBPM)** "
            "for [sample-test-project](https://vercel.com/apoorvapendses-projects/sample-test-project).\n"
            ">Update page.tsx ([5af715d](https://github.com/apoorvapendse/sample-test-project/commit/5af715d255d94d94fafee1d2254315e2b233c21c))"
        )

        self.check_webhook(
            "deployment_canceled",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_deployment_failed(self) -> None:
        """
        Test Vercel webhook for failed deployments.
        """
        expected_topic = "sample-project"
        expected_message = (
            "Deployment by apoorvapendse **[failed](https://vercel.com/apoorvapendses-projects/sample-project/Epq87qycdmXrX6hHMNodXFgFsBge)**."
            "\n>Update page.tsx ([d8282fc](https://github.com/apoorvapendse/sample-project/commit/d8282fc3c718d84ee3eb331a6e7a30f0790f3b69))"
        )
        self.check_webhook(
            "deployment_error",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_deployment_promoted(self) -> None:
        """
        Test Vercel webhook for promoted deployments.
        """
        expected_topic = "sample-project"
        expected_message = (
            "Deployment by apoorvapendse **[promoted](https://vercel.com/apoorvapendses-projects/sample-project/9mgbkQCUoQ36KykmXnkGtwCtAqSV)**."
            "\n>Update page.tsx ([5af715d](https://github.com/apoorvapendse/sample-project/commit/5af715d255d94d94fafee1d2254315e2b233c21c))"
        )
        self.check_webhook(
            "deployment_promoted",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_deployment_succeeded(self) -> None:
        """
        Test Vercel webhook for succeeded deployments.
        """
        expected_topic = "sample-project"
        expected_message = (
            "Production deployment by apoorvapendse **[succeeded](https://vercel.com/apoorvapendses-projects/sample-project/9mgbkQCUoQ36KykmXnkGtwCtAqSV)**."
            "\n>Update page.tsx ([5af715d](https://github.com/apoorvapendse/sample-project/commit/5af715d255d94d94fafee1d2254315e2b233c21c))"
        )
        self.check_webhook(
            "deployment_succeeded",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_ignore_unsupported_events(self) -> None:
        """
        Test Vercel webhook to ignore unsupported events.
        """
        self.check_webhook(
            "project_created", expected_topic_name=None, expected_message=None, expect_noop=True
        )
