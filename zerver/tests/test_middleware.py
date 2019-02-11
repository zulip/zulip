import re
import time
from typing import List

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

    @override_settings(SLOW_QUERY_LOGS_STREAM="logs")
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
                                 r"123\.456\.789\.012 SOCKET  200 10\.\ds .*")

    @override_settings(ERROR_BOT=None)
    @patch('logging.info')
    @patch('zerver.lib.actions.internal_send_message')
    def test_slow_query_log_without_error_bot(self, mock_internal_send_message: Mock,
                                              mock_logging_info: Mock) -> None:
        self.log_data['time_started'] = time.time() - self.SLOW_QUERY_TIME
        write_log_line(self.log_data, path='/socket/open', method='SOCKET',
                       remote_ip='123.456.789.012', email='unknown', client_name='?')
        mock_internal_send_message.assert_not_called()

class OpenGraphTest(ZulipTestCase):
    def check_title_and_description(self, path: str, title: str,
                                    in_description: List[str],
                                    not_in_description: List[str]) -> None:
        response = self.client_get(path)
        self.assertEqual(response.status_code, 200)
        decoded = response.content.decode('utf-8')
        for title_string in [
                '<meta property="og:title" content="{}">'.format(title),
                '<meta property="twitter:title" content="{}">'.format(title)]:
            self.assertIn(title_string, decoded)

        open_graph_description = re.search(  # type: ignore
            r'<meta property="og:description" content="(?P<description>[^>]*)">',
            decoded).group('description')
        twitter_description = re.search(  # type: ignore
            r'<meta name="twitter:description" content="(?P<description>[^>]*)">',
            decoded).group('description')
        for substring in in_description:
            self.assertIn(substring, open_graph_description)
            self.assertIn(substring, twitter_description)
        for substring in not_in_description:
            self.assertNotIn(substring, open_graph_description)
            self.assertNotIn(substring, twitter_description)

    def test_admonition_and_link(self) -> None:
        # disable-message-edit-history starts with an {!admin-only.md!}, and has a link
        # in the first paragraph.
        self.check_title_and_description(
            '/help/disable-message-edit-history',
            "Disable message edit history (Zulip Help Center)",
            ["By default, Zulip displays messages",
             "users can view the edit history of a message. To remove the",
             "best to delete the message entirely. "],
            ["Disable message edit history", "feature is only available", "Related articles",
             "Restrict message editing"]
        )

    def test_settings_tab(self) -> None:
        # deactivate-your-account starts with {settings_tab|your-account}
        self.check_title_and_description(
            '/help/deactivate-your-account',
            "Deactivate your account (Zulip Help Center)",
            ["Any bots that you maintain will be disabled. Deactivating "],
            ["Confirm by clicking", "  ", "\n"])

    def test_tabs(self) -> None:
        # logging-out starts with {start_tabs}
        self.check_title_and_description(
            '/help/logging-out',
            "Logging out (Zulip Help Center)",
            # Ideally we'd do something better here
            ["We're here to help! Email us at zulip-admin@example.com with questions, feedback, or " +
             "feature requests."],
            ["Click on the gear"])

    def test_index_pages(self) -> None:
        self.check_title_and_description(
            '/help/',
            "Zulip Help Center",
            [("Zulip is a group chat app. Its most distinctive characteristic is that "
              "conversation within an organization is divided into “streams” and further ")], [])

        self.check_title_and_description(
            '/api/',
            "Zulip API Documentation",
            [("Zulip's APIs allow you to integrate other services with Zulip. This "
              "guide should help you find the API you need:")], [])

    def test_nonexistent_page(self) -> None:
        response = self.client_get('/help/not-a-real-page')
        # Test that our open graph logic doesn't throw a 500
        self.assertEqual(response.status_code, 404)
        self.assert_in_response(
            # Probably we should make this "Zulip Help Center"
            '<meta property="og:title" content="No such article. (Zulip Help Center)">', response)
        self.assert_in_response('<meta property="og:description" content="No such article. '
                                'We\'re here to help! Email us at zulip-admin@example.com with questions, '
                                'feedback, or feature requests.">', response)
