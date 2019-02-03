from django.core import mail
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.pgp import pgp_sign_and_encrypt, PGPEmailMessage, PGPKeyNotFound
from zerver.models import UserProfile, UserPGP

from typing import List

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
        self.assertEqual(emails[0]._signed, True)
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
        self.assertEqual(emails[0]._encrypted, True)
        with self.assertRaises(NotImplementedError):
            emails[0].send()

    @override_settings(ENABLE_EMAIL_ENCRYPTION=True)
    @override_settings(ENABLE_EMAIL_SIGNATURES=True)
    def test_pgp_force_single_message(self) -> None:
        user_profiles = [self.example_user('hamlet'), self.example_user('cordelia')]
        user_pgps = []  # type: List[UserPGP]
        user_pgps.append(UserPGP(user_profile=user_profiles[0], public_key='dummy key 1'))
        user_pgps.append(UserPGP(user_profile=user_profiles[1], public_key='dummy key 2'))
        user_pgps[0].save()
        user_pgps[1].save()

        user_profiles[0].want_signed_emails = True
        user_profiles[0].want_encrypted_emails = True

        user_profiles[1].want_signed_emails = True
        user_profiles[1].want_encrypted_emails = True

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        emails = pgp_sign_and_encrypt(msg, user_profiles, force_single_message=True)

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]._signed, True)
        self.assertEqual(emails[0]._encrypted, True)

        user_profiles[0].want_signed_emails = False
        user_profiles[0].want_encrypted_emails = False

        user_profiles[1].want_signed_emails = False
        user_profiles[1].want_encrypted_emails = False

        emails = pgp_sign_and_encrypt(msg, user_profiles, force_single_message=True)

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]._signed, False)
        self.assertEqual(emails[0]._encrypted, False)

        user_profiles[0].want_signed_emails = True
        user_profiles[0].want_encrypted_emails = False

        user_profiles[1].want_signed_emails = True
        user_profiles[1].want_encrypted_emails = False

        emails = pgp_sign_and_encrypt(msg, user_profiles, force_single_message=True)

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]._signed, True)
        self.assertEqual(emails[0]._encrypted, False)

    @override_settings(ENABLE_EMAIL_ENCRYPTION=True)
    def test_pgp_missing_public_key(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.want_signed_emails = False
        user_profile.want_encrypted_emails = True

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        with self.assertRaises(PGPKeyNotFound):
            pgp_sign_and_encrypt(msg, [user_profile])
