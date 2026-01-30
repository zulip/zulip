from django.db import models
from django.db.models import Q

from zerver.lib.exceptions import (
    InvalidBouncerPublicKeyError,
    InvalidEncryptedPushRegistrationError,
    RequestExpiredError,
)
from zerver.models.users import UserProfile


class Device(models.Model):
    """Core zulip server table storing logged-in devices.

    Currently, only used by mobile apps for E2EE push notifications.
    """

    # The user on this server to whom this Device belongs.
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # Key to use to encrypt notifications for delivery to this device.
    # Consists of a 1-byte prefix identifying the symmetric cryptosystem
    # in use, followed by the secret key.
    # Prefix                 Cryptosystem
    #  0x31        libsodium's `crypto_secretbox_easy`
    push_key = models.BinaryField(null=True)
    # ID to reference the `push_key` - unsigned 32-bit integer.
    push_key_id = models.PositiveBigIntegerField(null=True)

    # ID to reference the token provided by FCM/APNs, registered to bouncer.
    push_token_id = models.BigIntegerField(null=True)
    # ID to reference the token provided by FCM/APNs, registration in progress to bouncer.
    pending_push_token_id = models.BigIntegerField(null=True)

    # The last time when `pending_push_token_id` was set to a new value.
    push_token_last_updated_timestamp = models.DateTimeField(null=True)

    class PushTokenKind(models.TextChoices):
        APNS = "apns", "APNs"
        FCM = "fcm", "FCM"

    push_token_kind = models.CharField(max_length=4, choices=PushTokenKind.choices, null=True)

    class PushRegistrationErrorCode(models.TextChoices):
        INVALID_BOUNCER_PUBLIC_KEY = InvalidBouncerPublicKeyError.code.name
        INVALID_ENCRYPTED_PUSH_REGISTRATION = InvalidEncryptedPushRegistrationError.code.name
        REQUEST_EXPIRED = RequestExpiredError.code.name

    # The error code returned when registration to bouncer fails.
    push_registration_error_code = models.CharField(
        max_length=100, choices=PushRegistrationErrorCode.choices, null=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(push_key_id__lte=2**32 - 1),
                name="push_key_id_lte_max_push_key_id",
            )
        ]
        indexes = [
            models.Index(
                # Used in 'get_recipient_info', `do_clear_mobile_push_notifications_for_ids`,
                # `prepare_payload_and_send_push_notifications`, `send_push_notifications`,
                # and `send_e2ee_test_push_notification_api`.
                fields=["user", "push_token_id"],
                condition=Q(push_token_id__isnull=False),
                name="zerver_device_user_push_token_id_idx",
            ),
        ]
