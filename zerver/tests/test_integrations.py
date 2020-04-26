from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.integrations import (
    split_fixture_path, get_fixture_and_image_paths, INTEGRATIONS, ScreenshotConfig, WebhookIntegration)

class IntegrationsTestCase(ZulipTestCase):

    def test_split_fixture_path(self) -> None:
        path = 'zerver/webhooks/semaphore/fixtures/push.json'
        integration_name, fixture_name = split_fixture_path(path)
        self.assertEqual(integration_name, 'semaphore')
        self.assertEqual(fixture_name, 'push')

    def test_get_fixture_and_image_paths(self) -> None:
        integration = INTEGRATIONS['airbrake']
        assert isinstance(integration, WebhookIntegration)
        screenshot_config = ScreenshotConfig('error_message.json', '002.png', 'ci')
        fixture_path, image_path = get_fixture_and_image_paths(integration, screenshot_config)
        self.assertEqual(fixture_path, 'zerver/webhooks/airbrake/fixtures/error_message.json')
        self.assertEqual(image_path, 'static/images/integrations/ci/002.png')
