from django.db import models

from zerver.lib.exceptions import (
    InvalidBouncerPublicKeyError,
    InvalidEncryptedPushRegistrationError,
    RequestExpiredError,
)
from zerver.models.users import UserProfile


class Device(models.Model):
    # The user on this server to whom this Device belongs.
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # Key to use to encrypt notifications for delivery to this device.
    # Consists of a 1-byte prefix identifying the symmetric cryptosystem
    # in use, followed by the secret key.
    # Prefix                 Cryptosystem
    #  0x31        libsodium's `crypto_secretbox_easy`
    push_key = models.BinaryField(null=True)
    push_key_id = models.BigIntegerField(null=True)

    push_token_id = models.BigIntegerField(null=True)
    pending_push_token_id = models.BigIntegerField(null=True)

    class TokenKind(models.TextChoices):
        APNS = "apns", "APNs"
        FCM = "fcm", "FCM"

    push_token_kind = models.CharField(max_length=4, choices=TokenKind.choices, null=True)

    class ErrorCode(models.TextChoices):
        INVALID_BOUNCER_PUBLIC_KEY = InvalidBouncerPublicKeyError.code.name
        INVALID_ENCRYPTED_PUSH_REGISTRATION = InvalidEncryptedPushRegistrationError.code.name
        REQUEST_EXPIRED = RequestExpiredError.code.name

    # The error code returned when registration to bouncer fails.
    # Set to NULL if the registration is in progress or successful.
    push_registration_error_code = models.CharField(
        max_length=100, choices=ErrorCode.choices, null=True
    )
