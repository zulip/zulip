import time

from unittest.mock import Mock, patch
from zerver.lib.test_classes import ZulipTestCase
from zerver.middleware import is_slow_query
from zerver.middleware import write_log_line

class SlowQueryTest(ZulipTestCase):
    def test_is_slow_query(self):
        # type: () -> None
        self.assertFalse(is_slow_query(1.1, '/some/random/url'))
        self.assertTrue(is_slow_query(2, '/some/random/url'))
        self.assertTrue(is_slow_query(5.1, '/activity'))
        self.assertFalse(is_slow_query(2, '/activity'))
        self.assertFalse(is_slow_query(2, '/json/report/error'))
        self.assertFalse(is_slow_query(2, '/api/v1/deployments/report_error'))
        self.assertFalse(is_slow_query(2, '/realm_activity/whatever'))
        self.assertFalse(is_slow_query(2, '/user_activity/whatever'))
        self.assertFalse(is_slow_query(9, '/accounts/webathena_kerberos_login/'))
        self.assertTrue(is_slow_query(11, '/accounts/webathena_kerberos_login/'))

    @patch('logging.info')
    def test_slow_query_log(self, mock_logging_info):
        # type: (Mock) -> None
        SLOW_QUERY_TIME = 10
        log_data = {'extra': '[transport=websocket]',
                    'time_started': time.time() - SLOW_QUERY_TIME,
                    'bugdown_requests_start': 0,
                    'bugdown_time_start': 0,
                    'remote_cache_time_start': 0,
                    'remote_cache_requests_start': 0}
        write_log_line(log_data, path='/socket/open', method='SOCKET',
                       remote_ip='123.456.789.012', email='unknown', client_name='?')
        last_message = self.get_last_message()
        self.assertEqual(last_message.sender.email, "error-bot@zulip.com")
        self.assertIn("logs", str(last_message.recipient))
        self.assertEqual(last_message.topic_name(), "testserver: slow queries")
        self.assertRegexpMatches(last_message.content,
                                 "123\.456\.789\.012 SOCKET  200 10\.0s .*")
