
from mock import Mock, patch

from zerver.apps import flush_cache
from zerver.lib.test_classes import ZulipTestCase

class AppsTest(ZulipTestCase):

    def test_cache_gets_flushed(self) -> None:
        zerver_config_mock = Mock()
        with patch('zerver.apps.cache.clear') as mock:
            flush_cache(zerver_config_mock)
            mock.assert_called_once()
