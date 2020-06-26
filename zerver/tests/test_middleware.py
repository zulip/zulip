import time
from typing import List
from unittest.mock import patch

from bs4 import BeautifulSoup

from zerver.lib.realm_icon import get_realm_icon_url
from zerver.lib.test_classes import ZulipTestCase
from zerver.middleware import is_slow_query, write_log_line
from zerver.models import get_realm


class SlowQueryTest(ZulipTestCase):
    SLOW_QUERY_TIME = 10
    log_data = {'extra': '[transport=websocket]',
                'time_started': 0,
                'markdown_requests_start': 0,
                'markdown_time_start': 0,
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

    def test_slow_query_log(self) -> None:
        self.log_data['time_started'] = time.time() - self.SLOW_QUERY_TIME
        with patch("zerver.middleware.slow_query_logger") as mock_slow_query_logger, \
                patch("zerver.middleware.logger") as mock_normal_logger:

            write_log_line(self.log_data, path='/some/endpoint/', method='GET',
                           remote_ip='123.456.789.012', requestor_for_logs='unknown', client_name='?')
            mock_slow_query_logger.info.assert_called_once()
            mock_normal_logger.info.assert_called_once()

            logged_line = mock_slow_query_logger.info.call_args_list[0][0][0]
            self.assertRegex(
                logged_line,
                r"123\.456\.789\.012 GET     200 10\.\ds .* \(unknown via \?\)",
            )

class OpenGraphTest(ZulipTestCase):
    def check_title_and_description(self, path: str, title: str,
                                    in_description: List[str],
                                    not_in_description: List[str],
                                    status_code: int=200) -> None:
        response = self.client_get(path)
        self.assertEqual(response.status_code, status_code)
        decoded = response.content.decode('utf-8')
        bs = BeautifulSoup(decoded, features='lxml')
        open_graph_title = bs.select_one('meta[property="og:title"]').get('content')
        self.assertEqual(open_graph_title, title)

        open_graph_description = bs.select_one('meta[property="og:description"]').get('content')
        for substring in in_description:
            self.assertIn(substring, open_graph_description)
        for substring in not_in_description:
            self.assertNotIn(substring, open_graph_description)

    def test_admonition_and_link(self) -> None:
        # disable-message-edit-history starts with an {!admin-only.md!}, and has a link
        # in the first paragraph.
        self.check_title_and_description(
            '/help/disable-message-edit-history',
            "Disable message edit history (Zulip Help Center)",
            ["By default, Zulip displays messages",
             "users can view the edit history of a message. | To remove the",
             "best to delete the message entirely. "],
            ["Disable message edit history", "feature is only available", "Related articles",
             "Restrict message editing"],
        )

    def test_settings_tab(self) -> None:
        # deactivate-your-account starts with {settings_tab|your-account}
        self.check_title_and_description(
            '/help/deactivate-your-account',
            "Deactivate your account (Zulip Help Center)",
            ["Any bots that you maintain will be disabled. | Deactivating "],
            ["Confirm by clicking", "  ", "\n"])

    def test_tabs(self) -> None:
        # logging-out starts with {start_tabs}
        self.check_title_and_description(
            '/help/logging-out',
            "Logging out (Zulip Help Center)",
            # Ideally we'd do something better here
            ["We're here to help! Email us at desdemona+admin@zulip.com with questions, feedback, or " +
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
        self.check_title_and_description(
            '/help/not-a-real-page',
            # Probably we should make this "Zulip Help Center"
            "No such article. (Zulip Help Center)",
            ["No such article. | We're here to help!",
             "Email us at desdemona+admin@zulip.com with questions, feedback, or feature requests."],
            [],
            # Test that our open graph logic doesn't throw a 500
            404)

    def test_login_page_simple_description(self) -> None:
        name = 'Zulip Dev'
        description = "The Zulip development environment default organization. It's great for testing!"

        self.check_title_and_description(
            '/login/',
            name,
            [description],
            [])

    def test_login_page_markdown_description(self) -> None:
        realm = get_realm('zulip')
        description = ("Welcome to **Clojurians Zulip** - the place where the Clojure community meets.\n\n"
                       "Before you signup/login:\n\n"
                       "* note-1\n"
                       "* note-2\n"
                       "* note-3\n\n"
                       "Enjoy!")
        realm.description = description
        realm.save(update_fields=['description'])

        self.check_title_and_description(
            '/login/',
            'Zulip Dev',
            ['Welcome to Clojurians Zulip - the place where the Clojure community meets',
             '* note-1 * note-2 * note-3 | Enjoy!'],
            [])

    def test_login_page_realm_icon(self) -> None:
        realm = get_realm('zulip')
        realm.icon_source = 'U'
        realm.save(update_fields=['icon_source'])
        realm_icon = get_realm_icon_url(realm)

        response = self.client_get('/login/')
        self.assertEqual(response.status_code, 200)

        decoded = response.content.decode('utf-8')
        bs = BeautifulSoup(decoded, features='lxml')
        open_graph_image = bs.select_one('meta[property="og:image"]').get('content')
        self.assertEqual(open_graph_image, f'{realm.uri}{realm_icon}')

    def test_login_page_realm_icon_absolute_url(self) -> None:
        realm = get_realm('zulip')
        realm.icon_source = 'U'
        realm.save(update_fields=['icon_source'])
        icon_url = f"https://foo.s3.amazonaws.com/{realm.id}/realm/icon.png?version={1}"
        with patch('zerver.lib.realm_icon.upload_backend.get_realm_icon_url', return_value=icon_url):
            response = self.client_get('/login/')
        self.assertEqual(response.status_code, 200)

        decoded = response.content.decode('utf-8')
        bs = BeautifulSoup(decoded, features='lxml')
        open_graph_image = bs.select_one('meta[property="og:image"]').get('content')
        self.assertEqual(open_graph_image, icon_url)

    def test_no_realm_api_page_og_url(self) -> None:
        response = self.client_get('/api/', subdomain='')
        self.assertEqual(response.status_code, 200)

        decoded = response.content.decode('utf-8')
        bs = BeautifulSoup(decoded, features='lxml')
        open_graph_url = bs.select_one('meta[property="og:url"]').get('content')

        self.assertTrue(open_graph_url.endswith('/api/'))
