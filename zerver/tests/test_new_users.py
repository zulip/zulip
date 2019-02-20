import datetime
from django.conf import settings
from django.core import mail
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.signals import get_device_browser, get_device_os, JUST_CREATED_THRESHOLD
from zerver.lib.actions import notify_new_user, do_change_notification_settings
from zerver.models import Recipient, Stream, Realm
from zerver.lib.initial_password import initial_password
from unittest import mock
from zerver.lib.timezone import get_timezone

class SendLoginEmailTest(ZulipTestCase):
    """
    Uses django's user_logged_in signal to send emails on new login.

    The receiver handler for this signal is always registered in production,
    development and testing, but emails are only sent based on SEND_LOGIN_EMAILS setting.

    SEND_LOGIN_EMAILS is set to true in default settings.
    It is turned off during testing.
    """

    def test_send_login_emails_if_send_login_email_setting_is_true(self) -> None:
        with self.settings(SEND_LOGIN_EMAILS=True):
            self.assertTrue(settings.SEND_LOGIN_EMAILS)
            # we don't use the self.login method since we spoof the user-agent
            utc = get_timezone('utc')
            mock_time = datetime.datetime(year=2018, month=1, day=1, tzinfo=utc)

            user = self.example_user('hamlet')
            user.timezone = 'US/Pacific'
            user.twenty_four_hour_time = False
            user.date_joined = mock_time - datetime.timedelta(seconds=JUST_CREATED_THRESHOLD + 1)
            user.save()
            password = initial_password(user.email)
            firefox_windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"
            user_tz = get_timezone(user.timezone)
            mock_time = datetime.datetime(year=2018, month=1, day=1, tzinfo=utc)
            reference_time = mock_time.astimezone(user_tz).strftime('%A, %B %d, %Y at %I:%M%p %Z')
            with mock.patch('zerver.signals.timezone_now', return_value=mock_time):
                self.client_post("/accounts/login/", info={"username": user.email, "password": password},
                                 HTTP_USER_AGENT=firefox_windows)

            # email is sent and correct subject
            self.assertEqual(len(mail.outbox), 1)
            subject = 'New login from Firefox on Windows'
            self.assertEqual(mail.outbox[0].subject, subject)
            # local time is correct and in email's body
            self.assertIn(reference_time, mail.outbox[0].body)

            # Try again with the 24h time format setting enabled for this user
            self.logout()  # We just logged in, we'd be redirected without this
            user.twenty_four_hour_time = True
            user.save()
            with mock.patch('zerver.signals.timezone_now', return_value=mock_time):
                self.client_post("/accounts/login/", info={"username": user.email, "password": password},
                                 HTTP_USER_AGENT=firefox_windows)

            reference_time = mock_time.astimezone(user_tz).strftime('%A, %B %d, %Y at %H:%M %Z')
            self.assertIn(reference_time, mail.outbox[1].body)

    def test_dont_send_login_emails_if_send_login_emails_is_false(self) -> None:
        self.assertFalse(settings.SEND_LOGIN_EMAILS)
        email = self.example_email('hamlet')
        self.login(email)

        self.assertEqual(len(mail.outbox), 0)

    def test_dont_send_login_emails_for_new_user_registration_logins(self) -> None:
        with self.settings(SEND_LOGIN_EMAILS=True):
            self.register("test@zulip.com", "test")

            # Verify that there's just 1 email for new user registration.
            self.assertEqual(mail.outbox[0].subject, "Activate your Zulip account")
            self.assertEqual(len(mail.outbox), 1)

    def test_without_path_info_dont_send_login_emails_for_new_user_registration_logins(self) -> None:
        with self.settings(SEND_LOGIN_EMAILS=True):
            self.client_post('/accounts/home/', {'email': "orange@zulip.com"})
            self.submit_reg_form_for_user("orange@zulip.com", "orange", PATH_INFO='')

            for email in mail.outbox:
                subject = 'New login from an unknown browser on an unknown operating system'
                self.assertNotEqual(email.subject, subject)

    @override_settings(SEND_LOGIN_EMAILS=True)
    def test_enable_login_emails_user_setting(self) -> None:
        user = self.example_user('hamlet')
        utc = get_timezone('utc')
        mock_time = datetime.datetime(year=2018, month=1, day=1, tzinfo=utc)

        user.timezone = 'US/Pacific'
        user.date_joined = mock_time - datetime.timedelta(seconds=JUST_CREATED_THRESHOLD + 1)
        user.save()

        do_change_notification_settings(user, "enable_login_emails", False)
        self.assertFalse(user.enable_login_emails)
        with mock.patch('zerver.signals.timezone_now', return_value=mock_time):
            self.login(user.email)
        self.assertEqual(len(mail.outbox), 0)

        do_change_notification_settings(user, "enable_login_emails", True)
        self.assertTrue(user.enable_login_emails)
        with mock.patch('zerver.signals.timezone_now', return_value=mock_time):
            self.login(user.email)
        self.assertEqual(len(mail.outbox), 1)


class TestBrowserAndOsUserAgentStrings(ZulipTestCase):

    def setUp(self) -> None:
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
            ('Mozilla/5.0 (iPhone; CPU iPhone OS 10_3 like Mac OS X) '
             'AppleWebKit/602.1.50 (KHTML, like Gecko) '
             'CriOS/56.0.2924.75 Mobile/14E5239e Safari/602.1', 'Chrome', 'iOS'),
            ('Mozilla/5.0 (iPad; CPU OS 6_1_3 like Mac OS X) ' +
                'AppleWebKit/536.26 (KHTML, like Gecko) ' +
                'Version/6.0 Mobile/10B329 Safari/8536.25', 'Safari', 'iOS'),
            ('Mozilla/5.0 (iPhone; CPU iPhone OS 6_1_4 like Mac OS X) ' +
                'AppleWebKit/536.26 (KHTML, like Gecko) Mobile/10B350', None, 'iOS'),
            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) ' +
                'AppleWebKit/537.36 (KHTML, like Gecko) ' +
                'Chrome/56.0.2924.87 Safari/537.36', 'Chrome', 'macOS'),
            ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) ' +
                'AppleWebKit/602.3.12 (KHTML, like Gecko) ' +
                'Version/10.0.2 Safari/602.3.12', 'Safari', 'macOS'),
            ('ZulipAndroid/1.0', 'Zulip', 'Android'),
            ('ZulipMobile/1.0.12 (Android 7.1.1)', 'Zulip', 'Android'),
            ('ZulipMobile/0.7.1.1 (iOS 10.3.1)', 'Zulip', 'iOS'),
            ('ZulipElectron/1.1.0-beta Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
             'AppleWebKit/537.36 (KHTML, like Gecko) Zulip/1.1.0-beta ' +
             'Chrome/56.0.2924.87 Electron/1.6.8 Safari/537.36', 'Zulip', 'Windows'),
            ('Mozilla/5.0 (X11; Linux i686) AppleWebKit/535.7 (KHTML, '
             'like Gecko) Ubuntu/11.10 Chromium/16.0.912.77 '
             'Chrome/16.0.912.77 Safari/535.7', 'Chromium', 'Linux'),
            ('Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/28.0.1500.52 Safari/537.36 '
             'OPR/15.0.1147.100', 'Opera', 'Windows'),
            ('Mozilla/5.0 (Windows NT 10.0; <64-bit tags>) AppleWebKit/'
             '<WebKit Rev> (KHTML, like Gecko) Chrome/<Chrome Rev> Safari'
             '/<WebKit Rev> Edge/<EdgeHTML Rev>.'
             '<Windows Build>', 'Edge', 'Windows'),
            ('Mozilla/5.0 (X11; CrOS x86_64 10895.56.0) AppleWebKit/537.36'
             '(KHTML, like Gecko) Chrome/69.0.3497.95 Safari/537.36',
             'Chrome', 'ChromeOS'),
            ('', None, None),
        ]

    def test_get_browser_on_new_login(self) -> None:
        for user_agent in self.user_agents:
            device_browser = get_device_browser(user_agent[0])
            self.assertEqual(device_browser, user_agent[1])

    def test_get_os_on_new_login(self) -> None:
        for user_agent in self.user_agents:
            device_os = get_device_os(user_agent[0])
            self.assertEqual(device_os, user_agent[2])


class TestNotifyNewUser(ZulipTestCase):
    def test_notify_of_new_user_internally(self) -> None:
        new_user = self.example_user('cordelia')
        self.make_stream('signups')
        notify_new_user(new_user, internal=True)

        message = self.get_last_message()
        actual_stream = Stream.objects.get(id=message.recipient.type_id)
        self.assertEqual(actual_stream.name, 'signups')
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertIn("**INTERNAL SIGNUP**", message.content)

    def test_notify_realm_of_new_user(self) -> None:
        new_user = self.example_user('cordelia')
        stream = self.make_stream(Realm.INITIAL_PRIVATE_STREAM_NAME)
        new_user.realm.signup_notifications_stream_id = stream.id
        new_user.realm.save()
        new_user = self.example_user('cordelia')
        notify_new_user(new_user)

        message = self.get_last_message()
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        actual_stream = Stream.objects.get(id=message.recipient.type_id)
        self.assertEqual(actual_stream.name, Realm.INITIAL_PRIVATE_STREAM_NAME)
        self.assertIn('@_**Cordelia Lear|%d** just signed up for Zulip.' % (new_user.id), message.content)
