from zerver.lib import encryption
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import PushDeviceToken

class EncryptionTests(ZulipTestCase):
    def test_encryption(self) -> None:
        data = 'Some super secret data' + chr(200)
        key = encryption.generate_encryption_key()

        encrypted_data = encryption.encrypt_data(key, data)
        self.assertNotEqual(data, encrypted_data)

        decrypted_data = encryption.decrypt_data(key, encrypted_data)
        self.assertEqual(data, decrypted_data)

    def test_get_device_key(self) -> None:
        hamlet = self.example_user('hamlet')
        key = encryption.generate_encryption_key()
        token = 'new-token'
        PushDeviceToken.objects.create(user=hamlet,
                                       token=token,
                                       notification_encryption_key=key,
                                       kind=PushDeviceToken.APNS)

        self.assertEqual(key, encryption.get_device_key(token))
