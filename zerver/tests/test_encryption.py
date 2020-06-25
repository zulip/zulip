from unittest import mock

from zerver.lib import encryption
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import PushDeviceToken


class EncryptionTests(ZulipTestCase):
    def test_encryption(self) -> None:
        data = 'les données secrètes'
        encoded_data = data.encode('utf-8')
        key = encryption.generate_encryption_key()

        encrypted_data, nonce = encryption.encrypt_data(key, encoded_data)
        self.assertNotEqual(data, encrypted_data)

        decrypted_data = encryption.decrypt_data(key, nonce, encrypted_data)
        self.assertEqual(data, decrypted_data)

    def test_generate_encryption_key(self) -> None:
        with mock.patch('cryptography.hazmat.primitives.ciphers.aead.AESGCM.generate_key', return_value=b'aaa'):
            hamlet = self.example_user('hamlet')
            key = encryption.generate_encryption_key()
            PushDeviceToken.objects.create(user=hamlet,
                                           notification_encryption_key=key,
                                           kind=PushDeviceToken.APNS)

            self.assertEqual(encryption.bytes_to_b64(b'aaa'), key)
