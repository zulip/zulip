# Simple one-time-pad library, to be used for encrypting Zulip API
# keys when sending them to the mobile apps via new standard mobile
# authentication flow.  This encryption is used to protect against
# credential-stealing attacks where a malicious app registers the
# zulip:// URL on a device, which might otherwise allow it to hijack a
# user's API key.
#
# The decryption logic here isn't actually used by the flow; we just
# have it here as part of testing the overall library.

import binascii
from zerver.models import UserProfile

def xor_hex_strings(bytes_a: str, bytes_b: str) -> str:
    """Given two hex strings of equal length, return a hex string with
    the bitwise xor of the two hex strings."""
    assert len(bytes_a) == len(bytes_b)
    return ''.join(["%x" % (int(x, 16) ^ int(y, 16))
                    for x, y in zip(bytes_a, bytes_b)])

def ascii_to_hex(input_string: str) -> str:
    """Given an ascii string, encode it as a hex string"""
    return "".join([hex(ord(c))[2:].zfill(2) for c in input_string])

def hex_to_ascii(input_string: str) -> str:
    """Given a hex array, decode it back to a string"""
    return binascii.unhexlify(input_string).decode('utf8')

def otp_encrypt_api_key(api_key: str, otp: str) -> str:
    assert len(otp) == UserProfile.API_KEY_LENGTH * 2
    hex_encoded_api_key = ascii_to_hex(api_key)
    assert len(hex_encoded_api_key) == UserProfile.API_KEY_LENGTH * 2
    return xor_hex_strings(hex_encoded_api_key, otp)

def otp_decrypt_api_key(otp_encrypted_api_key: str, otp: str) -> str:
    assert len(otp) == UserProfile.API_KEY_LENGTH * 2
    assert len(otp_encrypted_api_key) == UserProfile.API_KEY_LENGTH * 2
    hex_encoded_api_key = xor_hex_strings(otp_encrypted_api_key, otp)
    return hex_to_ascii(hex_encoded_api_key)

def is_valid_otp(otp: str) -> bool:
    try:
        assert len(otp) == UserProfile.API_KEY_LENGTH * 2
        [int(c, 16) for c in otp]
        return True
    except Exception:
        return False
