from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.integrations import split_fixture_path

class IntegrationsTestCase(ZulipTestCase):

    def test_split_fixture_path(self) -> None:
        path = 'zerver/webhooks/semaphore/fixtures/push.json'
        integration_name, fixture_name = split_fixture_path(path)
        self.assertEqual(integration_name, 'semaphore')
        self.assertEqual(fixture_name, 'push')
