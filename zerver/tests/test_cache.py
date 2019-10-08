from mock import Mock, patch

from zerver.apps import flush_cache
from zerver.lib.test_classes import ZulipTestCase

class AppsTest(ZulipTestCase):
    def test_cache_gets_flushed(self) -> None:
        with patch('zerver.apps.logging.info') as mock_logging:
            with patch('zerver.apps.cache.clear') as mock:
                # The argument to flush_cache doesn't matter
                flush_cache(Mock())
                mock.assert_called_once()
            mock_logging.assert_called_once()
