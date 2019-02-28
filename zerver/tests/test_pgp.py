from django.conf import settings
from django.core import mail
from django.core.mail import get_connection
from django.core.mail.message import SafeMIMEText, SafeMIMEMultipart

from email import message_from_bytes
from email.message import Message

from zerver.lib.email_helpers import get_message_part_by_type
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.pgp import (
    gpg_encrypt_content,
    gpg_decrypt_content,
    gpg_sign_content,
    gpg_verify_signature,
    pgp_sign_and_encrypt,
    PGPEmailMessage,
    PGPKeyNotFound,
    GPGSignatureFailed,
    GPGEncryptionFailed
)

from zerver.models import UserPGP

from typing import List, Dict
from unittest import mock

class PGPTestCase(ZulipTestCase):
    def example_user_keys(self, name: str) -> Dict[str, str]:
        data = self.fixture_data(name + '.asc', type='email/pgp')
        parts = data.split('====\n')
        keys = {}  # type: Dict[str, str]
        keys['privkey'] = parts[0]
        keys['pubkey'] = parts[1]

        return keys

    def check_signed_msg_structure(self, message: Message) -> None:
        self.assertTrue(message.is_multipart())
        self.assertEqual(message.get_content_subtype(), 'signed')
        self.assertEqual(message.get_param('protocol'), 'application/pgp-signature')

        parts = message.get_payload()
        assert isinstance(parts, List)
        assert isinstance(parts[1], Message)
        self.assertEqual(parts[1].get_content_type(), 'application/pgp-signature')
        signature = str(parts[1].get_payload())
        assert isinstance(parts[0], SafeMIMEText) or isinstance(parts[0], SafeMIMEMultipart)
        verify = gpg_verify_signature(signature, parts[0].as_bytes(linesep='\r\n'))
        self.assertTrue(verify)

    def check_encrypted_msg_structure(self, message: Message, decryption_key: str,
                                      expected_content: str, expect_signed: bool=False
                                      ) -> None:
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

        encrypted = str(parts[1].get_payload())
        decrypted, is_signed = gpg_decrypt_content(encrypted, decryption_key)
        self.assertEqual(expect_signed, is_signed)
        msg = message_from_bytes(decrypted)

        payload = msg.get_payload(decode=True)
        assert isinstance(payload, str) or isinstance(payload, bytes)
        if isinstance(payload, bytes):
            payload = payload.decode()

        # we need to ensure uniform convention for line endings
        payload = payload.replace('\r\n', '\n')
        expected_content = expected_content.replace('\r\n', '\n')
        self.assertEqual(payload, expected_content)

class TestGPGFunctions(PGPTestCase):
    def test_gpg_sign_success(self) -> None:
        data = b'test message'
        signature = gpg_sign_content(data)
        verify = gpg_verify_signature(signature, data)
        self.assertTrue(verify)

    def test_gpg_sign_broken_server_key(self) -> None:
        # when the server key is something broken, unimportable
        with mock.patch('zerver.lib.pgp._get_server_gpg_key',
                        return_value='dummykey'):
            with self.assertRaises(GPGSignatureFailed):
                gpg_sign_content(b'test message')

    def test_gpg_sign_server_key_public(self) -> None:
        # when the server key is a public key
        pubkey = self.example_user_keys('hamlet')['pubkey']
        with mock.patch('zerver.lib.pgp._get_server_gpg_key',
                        return_value=pubkey):
            with self.assertRaises(GPGSignatureFailed):
                gpg_sign_content(b'test message')

    def test_gpg_encrypt_success(self) -> None:
        data = b'test message'
        hamlet_keys = self.example_user_keys('hamlet')

        encrypted = gpg_encrypt_content(data, [hamlet_keys['pubkey']])
        decrypted, signed = gpg_decrypt_content(encrypted, hamlet_keys['privkey'])
        self.assertFalse(signed)
        self.assertEqual(data, decrypted)

        encrypted = gpg_encrypt_content(data, [hamlet_keys['pubkey']], sign=True)
        decrypted, signed = gpg_decrypt_content(encrypted, hamlet_keys['privkey'])
        self.assertTrue(signed)
        self.assertEqual(data, decrypted)

    def test_gpg_encrypt_multiple_recipients(self) -> None:
        data = b'test message'
        recipient_keys = [self.example_user_keys(name)['pubkey']
                          for name in ['hamlet', 'iago', 'othello']]

        encrypted = gpg_encrypt_content(data, recipient_keys, sign=True)
        # any of the recipients' keys can decrypt
        decryption_key = self.example_user_keys('iago')['privkey']
        decrypted, signed = gpg_decrypt_content(encrypted, decryption_key)
        self.assertTrue(signed)
        self.assertEqual(data, decrypted)

    def test_gpg_encrypt_broken_recipient_key(self) -> None:
        with self.assertRaises(GPGEncryptionFailed):
            gpg_encrypt_content(b'test message', ['dummykey'])

    def test_gpg_encrypt_and_sign_broken_server_key(self) -> None:
        data = b'test message'
        hamlet_keys = self.example_user_keys('hamlet')
        with mock.patch('zerver.lib.pgp._get_server_gpg_key',
                        return_value='dummykey'):
            with self.assertRaises(GPGEncryptionFailed):
                gpg_encrypt_content(data, [hamlet_keys['pubkey']], sign=True)

    def test_gpg_encrypt_and_sign_server_key_public(self) -> None:
        data = b'test message'
        hamlet_keys = self.example_user_keys('hamlet')

        pubkey = self.example_user_keys('othello')['pubkey']
        with mock.patch('zerver.lib.pgp._get_server_gpg_key',
                        return_value=pubkey):
            with self.assertRaises(GPGEncryptionFailed):
                gpg_encrypt_content(data, [hamlet_keys['pubkey']], sign=True)

    def test_gpg_encrypt_utf8_text(self) -> None:
        data = 'Gżegżółka'.encode()
        hamlet_keys = self.example_user_keys('hamlet')

        encrypted = gpg_encrypt_content(data, [hamlet_keys['pubkey']])
        decrypted, signed = gpg_decrypt_content(encrypted, hamlet_keys['privkey'])
        self.assertFalse(signed)
        self.assertEqual(data, decrypted)

    def test_gpg_sign_utf8_text(self) -> None:
        data = 'Gżegżółka'.encode()
        signature = gpg_sign_content(data)
        verify = gpg_verify_signature(signature, data)
        self.assertTrue(verify)

class TestPGPSignAndEncrypt(PGPTestCase):
    def setUp(self) -> None:
        hamlet_keys = self.example_user_keys('hamlet')
        othello_keys = self.example_user_keys('othello')
        iago_keys = self.example_user_keys('iago')

        user_profile = self.example_user('hamlet')
        user_pgp = UserPGP(user_profile=user_profile,
                           public_key=hamlet_keys['pubkey'])
        user_pgp.save()

        user_profile = self.example_user('othello')
        user_pgp = UserPGP(user_profile=user_profile,
                           public_key=othello_keys['pubkey'])
        user_pgp.save()

        user_profile = self.example_user('iago')
        user_pgp = UserPGP(user_profile=user_profile,
                           public_key=iago_keys['pubkey'])
        user_pgp.save()

    def tearDown(self) -> None:
        UserPGP.objects.all().delete()

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

    def test_pgp_sign_message(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.want_signed_emails = True
        user_profile.want_encrypted_emails = False

        msg = PGPEmailMessage(subject='Subject', body='Email\nbody')
        emails = pgp_sign_and_encrypt(msg, [user_profile])
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]._signed, True)
        self.check_signed_msg_structure(emails[0].message())

        emails[0].send()
        self.assertEqual(len(mail.outbox), 1)

    def test_pgp_encrypt_message(self) -> None:
        user_profile = self.example_user('hamlet')
        user_privkey = self.example_user_keys('hamlet')['privkey']
        user_profile.want_signed_emails = False
        user_profile.want_encrypted_emails = True

        msg = PGPEmailMessage(subject='Subject', body='Email\nbody')
        emails = pgp_sign_and_encrypt(msg, [user_profile])
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]._encrypted, True)
        self.check_encrypted_msg_structure(emails[0].message(),
                                           expected_content='Email\nbody',
                                           decryption_key=user_privkey)

        emails[0].send()
        self.assertEqual(len(mail.outbox), 1)

    def test_pgp_force_single_message(self) -> None:
        user_profiles = [self.example_user('hamlet'), self.example_user('othello')]
        othello_privkey = self.example_user_keys('othello')['privkey']

        user_profiles[0].want_signed_emails = True
        user_profiles[0].want_encrypted_emails = True

        user_profiles[1].want_signed_emails = True
        user_profiles[1].want_encrypted_emails = True

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        emails = pgp_sign_and_encrypt(msg, user_profiles, force_single_message=True)

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]._signed, True)
        self.assertEqual(emails[0]._encrypted, True)
        self.check_encrypted_msg_structure(emails[0].message(),
                                           decryption_key=othello_privkey,
                                           expected_content='Email body',
                                           expect_signed=True)

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

    def test_pgp_missing_public_key(self) -> None:
        user_profile = self.example_user('cordelia')
        user_profile.want_signed_emails = False
        user_profile.want_encrypted_emails = True

        msg = PGPEmailMessage(subject='Subject', body='Email body')
        with self.assertRaises(PGPKeyNotFound):
            pgp_sign_and_encrypt(msg, [user_profile])

class TestPGPEmailMessageClassInternals(PGPTestCase):
    def test_pgpemailmessage_setattr_lock(self) -> None:
        pgp_msg = PGPEmailMessage(body='text')
        pgp_msg._locked = True

        with self.assertRaises(AttributeError):
            pgp_msg.body = "text 2"

        # make sure connection can be set even when _locked
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

        self.assertEqual(msg._generated_message['From'], self.example_email('iago'))

    def test_pgpemailmessage_encrypt_utf8_text(self) -> None:
        hamlet_keys = self.example_user_keys('hamlet')
        msg = PGPEmailMessage(subject='Subject', body='Gżegżółka',
                              to=[self.example_email('hamlet')])
        msg.encrypt([hamlet_keys['pubkey']])
        self.check_encrypted_msg_structure(msg.message(), hamlet_keys['privkey'],
                                           expected_content='Gżegżółka')

    def test_pgpemailmessage_sign_utf8_text(self) -> None:
        msg = PGPEmailMessage(subject='Subject', body='Gżegżółka',
                              to=[self.example_email('hamlet')])
        msg.sign()
        self.check_signed_msg_structure(msg.message())

    def test_pgpemailmessage_encrypt_with_alternatives(self) -> None:
        hamlet_keys = self.example_user_keys('hamlet')

        text_content = 'This is an important message.'
        html_content = '<p>This is an <strong>important</strong> message.</p>'
        msg = PGPEmailMessage(subject='Subject', body=text_content,
                              to=[self.example_email('hamlet')])
        msg.attach_alternative(html_content, 'text/html')
        msg.encrypt([hamlet_keys['pubkey']])

        generated_message = msg.message()
        parts = generated_message.get_payload()
        assert isinstance(parts, List)
        assert isinstance(parts[1], Message)
        self.assertEqual(parts[1].get_content_type(), 'application/octet-stream')

        encrypted = str(parts[1].get_payload())
        decrypted = gpg_decrypt_content(encrypted, hamlet_keys['privkey'])[0]
        decrypted_msg = message_from_bytes(decrypted)

        self.assertEqual(decrypted_msg.get_content_type(), 'multipart/alternative')

        parts = decrypted_msg.get_payload()
        assert isinstance(parts, List)
        assert isinstance(parts[0], Message)
        assert isinstance(parts[1], Message)

        self.assertEqual(parts[0].get_content_type(), 'text/plain')
        self.assertEqual(parts[1].get_content_type(), 'text/html')

        decrypted_text = get_message_part_by_type(decrypted_msg, 'text/plain')
        decrypted_html = get_message_part_by_type(decrypted_msg, 'text/html')
        self.assertEqual(text_content, decrypted_text)
        self.assertEqual(html_content, decrypted_html)

    def test_pgpemailmessage_sign_with_alternatives(self) -> None:
        text_content = 'This is an important message.'
        html_content = '<p>This is an <strong>important</strong> message.</p>'
        msg = PGPEmailMessage(subject='Subject', body=text_content,
                              to=[self.example_email('hamlet')])
        msg.attach_alternative(html_content, 'text/html')
        msg.sign()

        self.check_signed_msg_structure(msg.message())
