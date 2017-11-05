import time

from django.test import override_settings
from unittest.mock import Mock, patch
from zerver.lib.test_classes import ZulipTestCase
from zerver.middleware import is_slow_query
from zerver.middleware import write_log_line

class SlowQueryTest(ZulipTestCase):
    SLOW_QUERY_TIME = 10
    log_data = {'extra': '[transport=websocket]',
                'time_started': 0,
                'bugdown_requests_start': 0,
                'bugdown_time_start': 0,
                'remote_cache_time_start': 0,
                'remote_cache_requests_start': 0}

    def test_is_slow_query(self) -> None:
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
    def test_slow_query_log(self, mock_logging_info: Mock) -> None:
        self.log_data['time_started'] = time.time() - self.SLOW_QUERY_TIME
        write_log_line(self.log_data, path='/socket/open', method='SOCKET',
                       remote_ip='123.456.789.012', email='unknown', client_name='?')
        last_message = self.get_last_message()
        self.assertEqual(last_message.sender.email, "error-bot@zulip.com")
        self.assertIn("logs", str(last_message.recipient))
        self.assertEqual(last_message.topic_name(), "testserver: slow queries")
        self.assertRegexpMatches(last_message.content,
                                 "123\.456\.789\.012 SOCKET  200 10\.\ds .*")

    @override_settings(ERROR_BOT=None)
    @patch('logging.info')
    @patch('zerver.lib.actions.internal_send_message')
    def test_slow_query_log_without_error_bot(self, mock_internal_send_message: Mock,
                                              mock_logging_info: Mock) -> None:
        self.log_data['time_started'] = time.time() - self.SLOW_QUERY_TIME
        write_log_line(self.log_data, path='/socket/open', method='SOCKET',
                       remote_ip='123.456.789.012', email='unknown', client_name='?')
        mock_internal_send_message.assert_not_called()
