import os

from zerver.lib.integrations import (
    INTEGRATIONS,
    NO_SCREENSHOT_WEBHOOKS,
    WEBHOOK_INTEGRATIONS,
    WEBHOOK_SCREENSHOT_CONFIG,
    WebhookIntegration,
    WebhookScreenshotConfig,
    get_fixture_path,
    get_image_path,
    split_fixture_path,
)
from zerver.lib.test_classes import ZulipTestCase


class IntegrationsTestCase(ZulipTestCase):
    def test_split_fixture_path(self) -> None:
        path = "zerver/webhooks/semaphore/fixtures/push.json"
        integration_name, fixture_name = split_fixture_path(path)
        self.assertEqual(integration_name, "semaphore")
        self.assertEqual(fixture_name, "push")

    def test_get_fixture_and_image_paths(self) -> None:
        integration = INTEGRATIONS["airbrake"]
        assert isinstance(integration, WebhookIntegration)
        screenshot_config = WebhookScreenshotConfig("error_message.json", "002.png", "ci")
        fixture_path = get_fixture_path(integration, screenshot_config)
        image_path = get_image_path(integration, screenshot_config)
        self.assertEqual(fixture_path, "zerver/webhooks/airbrake/fixtures/error_message.json")
        self.assertEqual(image_path, "static/images/integrations/ci/002.png")

    def test_get_bot_avatar_path(self) -> None:
        integration = INTEGRATIONS["alertmanager"]
        self.assertEqual(
            integration.get_bot_avatar_path(), "images/integrations/bot_avatars/prometheus.png"
        )

        # New instance with logo parameter not set
        integration = WebhookIntegration("alertmanager", ["misc"])
        self.assertIsNone(integration.get_bot_avatar_path())

    def test_no_missing_doc_screenshot_config(self) -> None:
        webhook_names = {webhook.name for webhook in WEBHOOK_INTEGRATIONS}
        webhooks_with_screenshot_config = set(WEBHOOK_SCREENSHOT_CONFIG.keys())
        missing_webhooks = webhook_names - webhooks_with_screenshot_config - NO_SCREENSHOT_WEBHOOKS
        message = (
            f"These webhooks are missing screenshot config: {missing_webhooks}.\n"
            "Add them to zerver.lib.integrations.DOC_SCREENSHOT_CONFIG"
        )
        self.assertFalse(missing_webhooks, message)

    def test_no_missing_screenshot_path(self) -> None:
        message = (
            '"{path}" does not exist for webhook {webhook_name}.\n'
            "Consider updating zerver.lib.integrations.DOC_SCREENSHOT_CONFIG\n"
            'and running "tools/screenshots/generate-integration-docs-screenshot" to keep the screenshots up-to-date.'
        )
        for integration_name in WEBHOOK_SCREENSHOT_CONFIG:
            configs = WEBHOOK_SCREENSHOT_CONFIG[integration_name]
            for screenshot_config in configs:
                integration = INTEGRATIONS[integration_name]
                assert isinstance(integration, WebhookIntegration)
                if screenshot_config.fixture_name == "":
                    # Such screenshot configs only use a placeholder
                    # fixture_name.
                    continue
                fixture_path = get_fixture_path(integration, screenshot_config)
                self.assertTrue(
                    os.path.isfile(fixture_path),
                    message.format(path=fixture_path, webhook_name=integration_name),
                )
                image_path = get_image_path(integration, screenshot_config)
                self.assertTrue(
                    os.path.isfile(image_path),
                    message.format(path=image_path, webhook_name=integration_name),
                )
