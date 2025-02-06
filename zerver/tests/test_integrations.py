import os
from typing import Annotated, TypeAlias
from unittest.mock import MagicMock, patch

from django.http import HttpRequest

from zerver.lib.integrations import (
    DOC_SCREENSHOT_CONFIG,
    INTEGRATIONS,
    NO_SCREENSHOT_WEBHOOKS,
    WEBHOOK_INTEGRATIONS,
    BaseScreenshotConfig,
    Integration,
    ScreenshotConfig,
    WebhookIntegration,
    get_fixture_and_image_paths,
    split_fixture_path,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.typed_endpoint import ApiParamConfig
from zerver.lib.webhooks.interfaced_settings import (
    SUPPORTED_INTERFACED_SETTINGS,
    MapToChannelsT,
    get_interfaced_settings_for,
)
from zerver.models import UserProfile


class IntegrationsTestCase(ZulipTestCase):
    def test_split_fixture_path(self) -> None:
        path = "zerver/webhooks/semaphore/fixtures/push.json"
        integration_name, fixture_name = split_fixture_path(path)
        self.assertEqual(integration_name, "semaphore")
        self.assertEqual(fixture_name, "push")

    def test_get_fixture_and_image_paths(self) -> None:
        integration = INTEGRATIONS["airbrake"]
        assert isinstance(integration, WebhookIntegration)
        screenshot_config = ScreenshotConfig("error_message.json", "002.png", "ci")
        fixture_path, image_path = get_fixture_and_image_paths(integration, screenshot_config)
        self.assertEqual(fixture_path, "zerver/webhooks/airbrake/fixtures/error_message.json")
        self.assertEqual(image_path, "static/images/integrations/ci/002.png")

    def test_get_fixture_and_image_paths_non_webhook(self) -> None:
        integration = INTEGRATIONS["nagios"]
        assert isinstance(integration, Integration)
        screenshot_config = BaseScreenshotConfig("service_notify.json", "001.png")
        fixture_path, image_path = get_fixture_and_image_paths(integration, screenshot_config)
        self.assertEqual(fixture_path, "zerver/integration_fixtures/nagios/service_notify.json")
        self.assertEqual(image_path, "static/images/integrations/nagios/001.png")

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
        webhooks_with_screenshot_config = set(DOC_SCREENSHOT_CONFIG.keys())
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
        for integration_name in DOC_SCREENSHOT_CONFIG:
            configs = DOC_SCREENSHOT_CONFIG[integration_name]
            for screenshot_config in configs:
                integration = INTEGRATIONS[integration_name]
                if screenshot_config.fixture_name == "":
                    # Such screenshot configs only use a placeholder
                    # fixture_name.
                    continue
                fixture_path, image_path = get_fixture_and_image_paths(
                    integration, screenshot_config
                )
                self.assertTrue(
                    os.path.isfile(fixture_path),
                    message.format(path=fixture_path, webhook_name=integration_name),
                )
                self.assertTrue(
                    os.path.isfile(image_path),
                    message.format(path=image_path, webhook_name=integration_name),
                )


SomeNewSettingT: TypeAlias = Annotated[bool, ApiParamConfig("abcabc")]

SUPPORTED_INTERFACED_SETTINGS_MOCK = {
    **SUPPORTED_INTERFACED_SETTINGS,
    "SomeNewSettingT": SomeNewSettingT,
}


class InterfacedSettingTestCase(ZulipTestCase):
    mocked_integration = WebhookIntegration("helloworld", ["monitoring"])

    def test_no_interfaced_settings(self) -> None:
        interfaced_settings = get_interfaced_settings_for(
            InterfacedSettingTestCase.mocked_integration
        )
        for value in interfaced_settings.values():
            self.assertIsNone(value)

    @patch.object(mocked_integration, "get_function")
    def test_map_to_channel_setting(self, mock_endpoint: MagicMock) -> None:
        def mock_api_hellosign_webhook(
            request: HttpRequest,
            user_profile: UserProfile,
            *,
            map_to_channel: MapToChannelsT,
        ) -> None:
            assert isinstance(map_to_channel, bool)  # nocoverage

        mock_endpoint.return_value = mock_api_hellosign_webhook

        interfaced_settings = get_interfaced_settings_for(self.mocked_integration)
        self.assertDictEqual(
            interfaced_settings,
            {
                "MapToChannelsT": {
                    "parameter_name": "map_to_channel",
                    "unique_query": "Z_map_to_channels",
                }
            },
        )

    @patch(
        "zerver.lib.webhooks.interfaced_settings.SUPPORTED_INTERFACED_SETTINGS",
        new=SUPPORTED_INTERFACED_SETTINGS_MOCK,
    )
    @patch.object(mocked_integration, "get_function")
    def test_unknown_setting(self, mock_endpoint: MagicMock) -> None:
        def mock_api_unknown_setting_webhook(
            request: HttpRequest,
            user_profile: UserProfile,
            *,
            some_new_setting: SomeNewSettingT,
        ) -> None:
            return  # nocoverage

        mock_endpoint.return_value = mock_api_unknown_setting_webhook
        with self.assertRaises(AssertionError) as e:
            get_interfaced_settings_for(self.mocked_integration)
        self.assertEqual(
            str(e.exception),
            "Please define a SettingContext for this setting: some_new_setting",
        )

    @patch.object(mocked_integration, "get_function")
    def test_using_multiple_identical_setting(self, mock_endpoint: MagicMock) -> None:
        def mock_api_hellosign_webhook(
            request: HttpRequest,
            user_profile: UserProfile,
            *,
            map_to_channel: MapToChannelsT,
            same_as_above: MapToChannelsT,
        ) -> None:
            assert isinstance(map_to_channel, bool)  # nocoverage

        mock_endpoint.return_value = mock_api_hellosign_webhook

        with self.assertRaises(AssertionError) as e:
            get_interfaced_settings_for(self.mocked_integration)
        self.assertEqual(
            str(e.exception),
            "Using multiple interfaced setting of the same kind is not supported. integration: helloworld, setting: MapToChannelsT",
        )
