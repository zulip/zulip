from django.utils.timezone import now as timezone_now

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import UserProfile
from zerver.models.devices import Device
from zerver.tornado.django_api import send_event_on_commit


def do_register_push_device(
    user_profile: UserProfile,
    device: Device,
    *,
    token_kind: str,
    push_key_bytes: bytes,
    push_key_id: int,
    token_id_int: int,
    token_id_base64: str,
) -> None:
    registered_at = timezone_now()
    device.push_key = push_key_bytes
    device.push_key_id = push_key_id
    device.pending_push_token_id = token_id_int
    device.push_token_kind = token_kind
    device.push_token_last_updated_timestamp = registered_at
    device.push_registration_error_code = None
    device.save(
        update_fields=[
            "push_key",
            "push_key_id",
            "pending_push_token_id",
            "push_token_kind",
            "push_token_last_updated_timestamp",
            "push_registration_error_code",
        ]
    )

    event = dict(
        type="device",
        op="update",
        device_id=device.id,
        push_key_id=device.push_key_id,
        pending_push_token_id=token_id_base64,
        push_token_last_updated_timestamp=datetime_to_timestamp(registered_at),
        push_registration_error_code=None,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])


def do_rotate_push_key(
    user_profile: UserProfile, device: Device, push_key_bytes: bytes, push_key_id: int
) -> None:
    if (
        device.push_key_id == push_key_id
        and device.push_key is not None
        and bytes(device.push_key) == push_key_bytes
    ):
        return

    device.push_key = push_key_bytes
    device.push_key_id = push_key_id
    device.save(update_fields=["push_key", "push_key_id"])

    event = dict(
        type="device",
        op="update",
        device_id=device.id,
        push_key_id=device.push_key_id,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])


def do_rotate_token(
    user_profile: UserProfile, device: Device, token_id_int: int, token_id_base64: str
) -> None:
    token_updated_at = timezone_now()
    device.pending_push_token_id = token_id_int
    device.push_token_last_updated_timestamp = token_updated_at
    device.push_registration_error_code = None
    device.save(
        update_fields=[
            "pending_push_token_id",
            "push_token_last_updated_timestamp",
            "push_registration_error_code",
        ]
    )
    event = dict(
        type="device",
        op="update",
        device_id=device.id,
        pending_push_token_id=token_id_base64,
        push_token_last_updated_timestamp=datetime_to_timestamp(token_updated_at),
        push_registration_error_code=None,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
