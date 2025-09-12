import os

from zerver.lib.integrations import (
    DOC_SCREENSHOT_CONFIG,
    INTEGRATIONS,
    NO_SCREENSHOT_CONFIG,
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
        integration_names = {integration.name for integration in INTEGRATIONS.values()}
        integrations_with_screenshot_configs = set(DOC_SCREENSHOT_CONFIG.keys())

        missing_integration_screenshots = (
            integration_names - integrations_with_screenshot_configs - NO_SCREENSHOT_CONFIG
        )
        extra_integration_configs = integrations_with_screenshot_configs - integration_names
        extra_integration_no_configs = NO_SCREENSHOT_CONFIG - integration_names

        def construct_message(title: str, integrations: set[str], action: str) -> str:
            return (
                f"\n\n{title}\n" + "\n".join(integrations) + f"\n{action}" if integrations else ""
            )

        self.assertEqual(
            integrations_with_screenshot_configs,
            integration_names - NO_SCREENSHOT_CONFIG,
            construct_message(
                "The following integrations are missing their example screenshot configuration:",
                missing_integration_screenshots,
                "Add them to zerver.lib.integrations.DOC_SCREENSHOT_CONFIG",
            )
            + construct_message(
                "The following integrations have a screenshot configuration but no longer exist:",
                extra_integration_configs,
                "Remove them from zerver.lib.integrations.DOC_SCREENSHOT_CONFIG",
            )
            + construct_message(
                "The following integrations are listed in NO_SCREENSHOT_CONFIG but no longer exist:",
                extra_integration_no_configs,
                "Remove them from zerver.lib.integrations.NO_SCREENSHOT_CONFIG",
            ),
        )

    def test_no_missing_screenshot_path(self) -> None:
        message = '"{path}" does not exist for integration {integration_name}.\n'
        tip = '\nConsider updating zerver.lib.integrations.DOC_SCREENSHOT_CONFIG\n and running "tools/screenshots/generate-integration-docs-screenshot" to keep the screenshots up-to-date.'
        error_message = ""

        for integration_name, screenshot_configs in DOC_SCREENSHOT_CONFIG.items():
            for screenshot_config in screenshot_configs:
                integration = INTEGRATIONS[integration_name]
                if isinstance(integration, WebhookIntegration):
                    assert isinstance(screenshot_config, WebhookScreenshotConfig)
                    if screenshot_config.fixture_name == "":
                        # Skip screenshot configs of webhooks with a placeholder fixture_name
                        continue
                    fixture_path = get_fixture_path(integration, screenshot_config)
                    error_message = (
                        error_message
                        + message.format(path=fixture_path, integration_name=integration_name)
                        if not os.path.isfile(fixture_path)
                        else error_message
                    )
                image_path = get_image_path(integration, screenshot_config)
                error_message = (
                    error_message
                    + message.format(path=image_path, integration_name=integration_name)
                    if not os.path.isfile(image_path)
                    else error_message
                )
        self.assertEqual(error_message, "", tip)
