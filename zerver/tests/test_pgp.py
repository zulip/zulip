from django.conf import settings
from django.core import mail
from django.core.mail import get_connection
from django.core.mail.message import SafeMIMEText
from django.test import override_settings

from email.message import Message

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.pgp import pgp_sign_and_encrypt, PGPEmailMessage, PGPKeyNotFound
from zerver.models import UserProfile, UserPGP

from typing import List, Dict

class TestPGP(ZulipTestCase):
    def check_signed_msg_structure(self, message: Message) -> None:
        self.assertTrue(message.is_multipart())
        self.assertEqual(message.get_content_subtype(), 'signed')
        self.assertEqual(message.get_param('protocol'), 'application/pgp-signature')

        parts = message.get_payload()
        assert isinstance(parts, List)
        assert isinstance(parts[1], Message)
        self.assertEqual(parts[1].get_content_type(), 'application/pgp-signature')
        self.assertEqual(parts[1].get_payload(), 'dummysignature')

    def check_encrypted_msg_structure(self, message: Message,
                                      signed: bool=False) -> None:
        self.assertTrue(message.is_multipart())
        self.assertEqual(message.get_content_subtype(), 'encrypted')
        self.assertEqual(message.get_param('protocol'), 'application/pgp-encrypted')

        parts = message.get_payload()
        assert isinstance(parts, List)
        assert isinstance(parts[0], Message)
        assert isinstance(parts[1], Message)
        self.assertEqual(parts[0].get_content_type(), 'application/pgp-encrypted')
        self.assertEqual(parts[0].get_payload(), 'Version: 1')
        self.assertEqual(parts[1].get_content_type(), 'application/octet-stream')
        expected_payload = 'dummysignedciphertext' if signed else 'dummyciphertext'
        self.assertEqual(parts[1].get_payload(), expected_payload)

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
        self.check_signed_msg_structure(emails[0].message())

        emails[0].send()
        self.assertEqual(len(mail.outbox), 1)

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
        self.check_encrypted_msg_structure(emails[0].message())

        emails[0].send()
        self.assertEqual(len(mail.outbox), 1)

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
        self.check_encrypted_msg_structure(emails[0].message(), signed=True)

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
        self.check_signed_msg_structure(emails[0].message())

    @override_settings(ENABLE_EMAIL_ENCRYPTION=True)
    def test_pgp_missing_public_key(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.want_signed_emails = False
        user_profile.want_encrypted_emails = True

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        with self.assertRaises(PGPKeyNotFound):
            pgp_sign_and_encrypt(msg, [user_profile])

    def test_pgpemailmessage_setattr_lock(self) -> None:
        pgp_msg = PGPEmailMessage(body='text')
        pgp_msg._locked = True

        with self.assertRaises(AttributeError):
            pgp_msg.body = "text 2"

        conn = get_connection()
        pgp_msg.connection = conn
        self.assertEqual(pgp_msg.connection, conn)

        pgp_msg._locked = False
        pgp_msg.body = "text 3"
        self.assertEqual(pgp_msg.body, 'text 3')

    def test_pgpemailmessage_set_headers(self) -> None:
        headers = {}  # type: Dict[str, str]
        headers['Custom-Header'] = 'some content'
        headers['From'] = self.example_email('iago')
        msg = PGPEmailMessage(subject='Subject', body='Email body',
                              to=[self.example_email('hamlet')],
                              headers=headers,
                              cc=[self.example_email('cordelia')],
                              reply_to=[settings.DEFAULT_FROM_EMAIL])
        original_message = msg.message()
        msg._generated_message = SafeMIMEText("text")

        msg._set_headers()
        headers_list = ['Custom-Header', 'Subject', 'To', 'Cc', 'Reply-To']
        assert msg._generated_message is not None
        for header in headers_list:
            self.assertEqual(msg._generated_message[header],
                             original_message[header])
