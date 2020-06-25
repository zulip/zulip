import orjson

from zerver.lib import encryption
from zerver.lib.test_classes import ZulipTestCase


class EncryptionTests(ZulipTestCase):
    def test_encrypt_decrypt(self) -> None:
        key = encryption.generate_encryption_key()
        self.assert_length(key, 16)

        data = {"text": "les données secrètes"}
        encoded_data = orjson.dumps(data)

        encrypted_data, nonce = encryption.encrypt_data(key, encoded_data)
        self.assertNotEqual(data, encrypted_data)

        # Simulate the use case when we have to transmit the encrypted data in
        # JSON to a third-party
        payload = {
            "encrypted_data": encryption.bytes_to_b64(encrypted_data),
            "nonce": encryption.bytes_to_b64(nonce),
        }

        decrypted_data = encryption.decrypt_data(
            key,
            encryption.b64_to_bytes(payload["nonce"]),
            encryption.b64_to_bytes(payload["encrypted_data"]),
        )
        self.assertEqual(data, orjson.loads(decrypted_data))
