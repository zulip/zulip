from django.conf import settings
from django.core import mail
from django.contrib.auth.signals import user_logged_in
from zerver.lib.test_classes import ZulipTestCase
from zerver.signals import get_device_browser, get_device_os
from zerver.lib.actions import notify_new_user
from zerver.models import Recipient, Stream

class SendLoginEmailTest(ZulipTestCase):
    """
    Uses django's user_logged_in signal to send emails on new login.

    The receiver handler for this signal is always registered in production,
    development and testing, but emails are only sent based on SEND_LOGIN_EMAILS setting.

    SEND_LOGIN_EMAILS is set to true in default settings.
    It is turned off during testing.
    """

    def test_send_login_emails_if_send_login_email_setting_is_true(self):
        # type: () -> None
        with self.settings(SEND_LOGIN_EMAILS=True):
            self.assertTrue(settings.SEND_LOGIN_EMAILS)
            email = self.example_email('hamlet')
            self.login(email)

            # email is sent and correct subject
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].subject, 'A new login to your Zulip account.')

    def test_dont_send_login_emails_if_send_login_emails_is_false(self):
        # type: () -> None
        self.assertFalse(settings.SEND_LOGIN_EMAILS)
        email = self.example_email('hamlet')
        self.login(email)

        self.assertEqual(len(mail.outbox), 0)

    def test_dont_send_login_emails_for_new_user_registration_logins(self):
        # type: () -> None
        with self.settings(SEND_LOGIN_EMAILS=True):
            self.register("test@zulip.com", "test")

            for email in mail.outbox:
                self.assertNotEqual(email.subject, 'A new login to your Zulip account.')

    def test_without_path_info_dont_send_login_emails_for_new_user_registration_logins(self):
        # type: () -> None
        with self.settings(SEND_LOGIN_EMAILS=True):
            self.client_post('/accounts/home/', {'email': "orange@zulip.com"})
            self.submit_reg_form_for_user("orange@zulip.com", "orange", PATH_INFO='')

            for email in mail.outbox:
                self.assertNotEqual(email.subject, 'A new login to your Zulip account.')

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
            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) ' +
                'AppleWebKit/602.3.12 (KHTML, like Gecko) ' +
                'Version/10.0.2 Safari/602.3.12', 'Safari', 'MacOS'),
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


class TestNotifyNewUser(ZulipTestCase):
    def test_notify_of_new_user_internally(self):
        # type: () -> None
        new_user = self.example_user('cordelia')
        self.make_stream('signups')
        notify_new_user(new_user, internal=True)

        message = self.get_last_message()
        actual_stream = Stream.objects.get(id=message.recipient.type_id)
        self.assertEqual(actual_stream.name, 'signups')
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertIn("**INTERNAL SIGNUP**", message.content)
