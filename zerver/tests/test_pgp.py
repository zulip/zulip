from django.core import mail
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.pgp import pgp_sign_and_encrypt, PGPEmailMessage
from zerver.models import UserProfile, UserPGP

class TestPGP(ZulipTestCase):
    @override_settings(ENABLE_EMAIL_ENCRYPTION=True)
    @override_settings(ENABLE_EMAIL_SIGNATURES=True)
    def test_pgp_vanilla_message(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.want_signed_emails = False
        user_profile.want_encrypted_emails = False

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        emails = pgp_sign_and_encrypt(msg, [user_profile])

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0].subject, 'Subject')
        self.assertEqual(emails[0].body, 'Email body')

        emails[0].send()
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(ENABLE_EMAIL_ENCRYPTION=True)
    @override_settings(ENABLE_EMAIL_SIGNATURES=True)
    def test_pgp_sign_message(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.want_signed_emails = True
        user_profile.want_encrypted_emails = False

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        emails = pgp_sign_and_encrypt(msg, [user_profile])
        self.assertEqual(len(emails), 1)
        with self.assertRaises(NotImplementedError):
            emails[0].send()

    @override_settings(ENABLE_EMAIL_ENCRYPTION=True)
    @override_settings(ENABLE_EMAIL_SIGNATURES=True)
    def test_pgp_encrypt_message(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.want_signed_emails = False
        user_profile.want_encrypted_emails = True

        user_pgp = UserPGP(user_profile=user_profile, public_key='dummy key')
        user_pgp.save()

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        emails = pgp_sign_and_encrypt(msg, [user_profile])
        self.assertEqual(len(emails), 1)
        with self.assertRaises(NotImplementedError):
            emails[0].send()
