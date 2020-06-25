import base64
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def bytes_to_b64(data: bytes) -> str:
    """
    Converts bytes to url-safe base64 encoded string.
    """
    return base64.b64encode(data).decode('utf-8')

def b64_to_bytes(data: str) -> bytes:
    """
    Converts url-safe base64 encoded string to bytes.
    """
    return base64.b64decode(data.encode('utf-8'))

def encrypt_data(key: str, data: bytes) -> Tuple[str, str]:
    """
    Returns a tuple of `(encrypted_data, nonce)`.
    """
    # AESGCM() expects key as bytes.
    aesgcm = AESGCM(b64_to_bytes(key))
    nonce = os.urandom(12)
    # AESGCM.encrypt() expects data in bytes and returns ciphertext
    # bytes with the 16 byte tag appended.
    encrypted_data = aesgcm.encrypt(nonce, data, None)
    return bytes_to_b64(encrypted_data), bytes_to_b64(nonce)

def decrypt_data(key: str, nonce: str, encrypted_data: str) -> str:
    # AESGCM() expects key as bytes.
    aesgcm = AESGCM(b64_to_bytes(key))
    # AESGCM.decrypt() expects encrypted data and nonce as bytes.
    data = aesgcm.decrypt(b64_to_bytes(nonce),
                          b64_to_bytes(encrypted_data),
                          None)
    # Return unicode data.
    return data.decode('utf-8')

def generate_encryption_key() -> str:
    key = AESGCM.generate_key(bit_length=128)
    # generate_key() returns key as bytes. We covert it to base64
    # and store it as a string in the DB.
    return bytes_to_b64(key)
