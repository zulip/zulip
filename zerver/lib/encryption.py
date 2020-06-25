import base64
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AESGCM_KEY_LENGTH_IN_BYTES = 16  # 128 bits


def bytes_to_b64(data: bytes) -> str:
    """
    Converts bytes to url-safe base64 encoded string.
    Use this when the encrypted data
    """
    return base64.b64encode(data).decode("utf-8")


def b64_to_bytes(data: str) -> bytes:
    """
    Converts url-safe base64 encoded string to bytes.
    """
    return base64.b64decode(data.encode("utf-8"))


def encrypt_data(key: bytes, data: bytes) -> Tuple[bytes, bytes]:
    """
    Returns a tuple of `(encrypted_data, nonce)`.
    """
    # AESGCM() expects key as bytes.
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    # AESGCM.encrypt() expects data in bytes and returns ciphertext
    # bytes with the 16 byte tag appended.
    encrypted_data = aesgcm.encrypt(nonce, data, None)
    return encrypted_data, nonce


def decrypt_data(key: bytes, nonce: bytes, encrypted_data: bytes) -> bytes:
    # AESGCM() expects key as bytes.
    aesgcm = AESGCM(key)
    # AESGCM.decrypt() expects encrypted data and nonce as bytes.
    data = aesgcm.decrypt(nonce, encrypted_data, None)
    # Return unicode data.
    return data


def generate_encryption_key() -> bytes:
    return AESGCM.generate_key(bit_length=AESGCM_KEY_LENGTH_IN_BYTES * 8)
