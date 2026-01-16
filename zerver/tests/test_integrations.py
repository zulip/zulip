import os

from zerver.lib.integrations import (
    BOT_INTEGRATIONS,
    EMBEDDED_BOTS,
    EMBEDDED_INTEGRATIONS,
    HUBOT_INTEGRATIONS,
    INCOMING_WEBHOOK_INTEGRATIONS,
    INTEGRATIONS,
    NO_SCREENSHOT_CONFIG,
    PLUGIN_INTEGRATIONS,
    PYTHON_API_INTEGRATIONS,
    STANDALONE_REPO_INTEGRATIONS,
    VIDEO_CALL_INTEGRATIONS,
    ZAPIER_INTEGRATIONS,
    BotIntegration,
    HubotIntegration,
    IncomingWebhookIntegration,
    Integration,
    PythonAPIIntegration,
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
        assert isinstance(integration, IncomingWebhookIntegration)
        screenshot_config = WebhookScreenshotConfig("error_message.json", "002.png", "ci")
        fixture_path = get_fixture_path(integration, screenshot_config)
        image_path = get_image_path(integration, screenshot_config)
        self.assertEqual(fixture_path, "zerver/webhooks/airbrake/fixtures/error_message.json")
        self.assertEqual(image_path, "static/images/integrations/ci/002.png")

    def test_get_logo_path(self) -> None:
        # Test with an integration that passed logo as an argument
        integration = INTEGRATIONS["slack_incoming"]
        with self.assertRaises(AssertionError):
            integration.get_logo_path()

        # Test with an integration that has only a PNG option
        integration = INTEGRATIONS["onyx"]
        self.assertEqual(integration.get_logo_path(), "images/integrations/logos/onyx.png")

        # Test the fallback logo with an embedded integration without a logo
        ZULIP_LOGO_STATIC_PATH_PNG = "images/logo/zulip-icon-128x128.png"
        integration = EMBEDDED_BOTS[0]
        with self.assertRaises(AssertionError):
            integration.get_logo_path()
        self.assertEqual(
            integration.get_logo_path(ZULIP_LOGO_STATIC_PATH_PNG), ZULIP_LOGO_STATIC_PATH_PNG
        )

        # Test with a bot integration that has a logo
        # They use different DEFAULT_* paths.
        integration = INTEGRATIONS["xkcd"]
        logo_path = integration.get_logo_path()
        self.assertEqual(logo_path, "generated/bots/xkcd/logo.png")
        self.assertTrue(logo_path.startswith("generated/bots/"))

    def test_get_bot_avatar_path(self) -> None:
        integration = INTEGRATIONS["alertmanager"]
        self.assertEqual(
            integration.get_bot_avatar_path(), "images/integrations/bot_avatars/prometheus.png"
        )

        with self.assertRaises(AssertionError):
            integration = Integration("alertmanager", ["misc"])

    def test_no_missing_doc_screenshot_config(self) -> None:
        integration_names = {
            integration.name
            for integration in INTEGRATIONS.values()
            if integration.is_enabled_in_catalog()
        }
        integrations_with_screenshot_configs = {
            integration_name
            for integration_name, integration in INTEGRATIONS.items()
            if integration.screenshot_configs
        }

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
                "Add them to zerver.lib.integrations.INTEGRATIONS",
            )
            + construct_message(
                "The following integrations have a screenshot configuration but no longer exist:",
                extra_integration_configs,
                "Remove them from zerver.lib.integrations.INTEGRATIONS",
            )
            + construct_message(
                "The following integrations are listed in NO_SCREENSHOT_CONFIG but no longer exist:",
                extra_integration_no_configs,
                "Remove them from zerver.lib.integrations.NO_SCREENSHOT_CONFIG",
            ),
        )

    def test_no_missing_screenshot_path(self) -> None:
        message = '"{path}" does not exist for integration {integration_name}.\n'
        tip = '\nConsider updating screenshot configs in zerver.lib.integrations.INTEGRATIONS\n and running "tools/screenshots/generate-integration-docs-screenshot" to keep the screenshots up-to-date.'
        error_message = ""

        for integration in INTEGRATIONS.values():
            if integration.screenshot_configs is None:
                continue
            for screenshot_config in integration.screenshot_configs:
                if isinstance(integration, IncomingWebhookIntegration):
                    assert isinstance(screenshot_config, WebhookScreenshotConfig)
                    if screenshot_config.fixture_name == "":
                        # Skip screenshot configs of webhooks with a placeholder fixture_name
                        continue
                    fixture_path = get_fixture_path(integration, screenshot_config)
                    error_message = (
                        error_message
                        + message.format(path=fixture_path, integration_name=integration.name)
                        if not os.path.isfile(fixture_path)
                        else error_message
                    )
                image_path = get_image_path(integration, screenshot_config)
                error_message = (
                    error_message
                    + message.format(path=image_path, integration_name=integration.name)
                    if not os.path.isfile(image_path)
                    else error_message
                )
        self.assertEqual(error_message, "", tip)

    def test_sorting(self) -> None:
        integration_lists: dict[
            str,
            list[Integration]
            | list[IncomingWebhookIntegration]
            | list[BotIntegration]
            | list[HubotIntegration]
            | list[PythonAPIIntegration],
        ] = {
            "INCOMING_WEBHOOK_INTEGRATIONS": INCOMING_WEBHOOK_INTEGRATIONS,
            "PYTHON_API_INTEGRATIONS": PYTHON_API_INTEGRATIONS,
            "BOT_INTEGRATIONS": BOT_INTEGRATIONS,
            "HUBOT_INTEGRATIONS": HUBOT_INTEGRATIONS,
            "VIDEO_CALL_INTEGRATIONS": VIDEO_CALL_INTEGRATIONS,
            "EMBEDDED_INTEGRATIONS": EMBEDDED_INTEGRATIONS,
            "ZAPIER_INTEGRATIONS": ZAPIER_INTEGRATIONS,
            "PLUGIN_INTEGRATIONS": PLUGIN_INTEGRATIONS,
            "STANDALONE_REPO_INTEGRATIONS": STANDALONE_REPO_INTEGRATIONS,
        }

        errors: list[str] = []

        for list_name, integration_list in integration_lists.items():
            names = [integration.name for integration in integration_list]
            errors.extend(
                f"{list_name} is not sorted: '{names[i]}' > '{names[i + 1]}'"
                for i in range(len(names) - 1)
                if names[i] > names[i + 1]
            )

        assert not errors, "\n".join(errors)

    def test_embedded_bots_are_disabled_in_catalog(self) -> None:
        for embedded_bot in EMBEDDED_BOTS:
            self.assertFalse(
                embedded_bot.is_enabled_in_catalog(),
                f"Embedded bot '{embedded_bot.name}' should be disabled from the catalog.",
            )
