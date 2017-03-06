from zerver.lib.test_classes import ZulipTestCase
from zerver.signals import get_device_browser, get_device_os


class TestBrowserAndOsUserAgentStrings(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        self.user_agents = [
            ('mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) ' +
                'Chrome/54.0.2840.59 Safari/537.36', 'Chrome', 'Linux',),
            ('mozilla/5.0 (windows nt 6.1; win64; x64) applewebkit/537.36 (khtml, like gecko) ' +
                'chrome/56.0.2924.87 safari/537.36', 'Chrome', 'Windows',),
            ('mozilla/5.0 (windows nt 6.1; wow64; rv:51.0) ' +
                'gecko/20100101 firefox/51.0', 'Firefox', 'Windows',),
            ('mozilla/5.0 (windows nt 6.1; wow64; trident/7.0; rv:11.0) ' +
                'like gecko', 'Internet Explorer', 'Windows'),
            ('Mozilla/5.0 (Android; Mobile; rv:27.0) ' +
                'Gecko/27.0 Firefox/27.0', 'Firefox', 'Android'),
            ('Mozilla/5.0 (iPad; CPU OS 6_1_3 like Mac OS X) ' +
                'AppleWebKit/536.26 (KHTML, like Gecko) ' +
                'Version/6.0 Mobile/10B329 Safari/8536.25', 'Safari', 'iOS'),
            ('Mozilla/5.0 (iPhone; CPU iPhone OS 6_1_4 like Mac OS X) ' +
                'AppleWebKit/536.26 (KHTML, like Gecko) Mobile/10B350', None, 'iOS'),
            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) ' +
                'AppleWebKit/537.36 (KHTML, like Gecko) ' +
                'Chrome/56.0.2924.87 Safari/537.36', 'Chrome', 'MacOS'),
            ('', None, None),
        ]

    def test_get_browser_on_new_login(self):
        # type: () -> None
        for user_agent in self.user_agents:
            device_browser = get_device_browser(user_agent[0])
            self.assertEqual(device_browser, user_agent[1])

    def test_get_os_on_new_login(self):
        # type: () -> None
        for user_agent in self.user_agents:
            device_os = get_device_os(user_agent[0])
            self.assertEqual(device_os, user_agent[2])
