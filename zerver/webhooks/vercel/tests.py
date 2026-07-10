from zerver.lib.test_classes import WebhookTestCase


class VercelHookTests(WebhookTestCase):
    def test_deployment_created(self) -> None:
        expected_topic_name = "my-app"
        expected_message = "Deployment of [my-app](https://vercel.com/acme/my-app/dpl_00000000000000000000000001) to **preview** has started."
        self.check_webhook("deployment_created", expected_topic_name, expected_message)

    def test_deployment_succeeded(self) -> None:
        expected_topic_name = "my-app"
        expected_message = "Deployment of [my-app](https://vercel.com/acme/my-app/dpl_00000000000000000000000002) to **production** is ready :check:."
        self.check_webhook("deployment_succeeded", expected_topic_name, expected_message)

    def test_deployment_error(self) -> None:
        expected_topic_name = "my-app"
        expected_message = "Deployment of [my-app](https://vercel.com/acme/my-app/dpl_00000000000000000000000003) to **production** failed :cross_mark:."
        self.check_webhook("deployment_error", expected_topic_name, expected_message)

    def test_deployment_canceled(self) -> None:
        expected_topic_name = "my-app"
        expected_message = "Deployment of [my-app](https://vercel.com/acme/my-app/dpl_00000000000000000000000004) to **production** was canceled."
        self.check_webhook("deployment_canceled", expected_topic_name, expected_message)

    def test_deployment_promoted(self) -> None:
        expected_topic_name = "my-app"
        expected_message = "Deployment of [my-app](https://vercel.com/acme/my-app/dpl_00000000000000000000000005) to **production** was promoted."
        self.check_webhook("deployment_promoted", expected_topic_name, expected_message)
