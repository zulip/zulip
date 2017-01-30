from django.conf import settings
from django.core import mail
from django.contrib.auth.signals import user_logged_in
from zerver.lib.test_classes import ZulipTestCase


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
            self.login("hamlet@zulip.com")

            # email is sent and correct subject
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].subject, 'A new login to your Zulip account.')

    def test_dont_send_login_emails_if_send_login_emails_is_false(self):
        # type: () -> None
        self.assertFalse(settings.SEND_LOGIN_EMAILS)
        self.login("hamlet@zulip.com")

        self.assertEqual(len(mail.outbox), 0)
