import base64
import binascii

from django.utils.translation import gettext as _
from typing_extensions import TypedDict

from zerver.lib.exceptions import JsonableError
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models.devices import Device
from zerver.models.users import UserProfile


class DeviceInfoDict(TypedDict):
    push_key_id: int | None
    push_token_id: str | None
    pending_push_token_id: str | None
    push_token_last_updated_timestamp: int | None
    push_registration_error_code: str | None


def b64encode_token_id(token_id: int) -> str:
    token_id_bytes = token_id.to_bytes(8, byteorder="big", signed=True)
    return base64.b64encode(token_id_bytes).decode()


def b64decode_token_id(token_id_base64: str) -> int:
    try:
        token_id_bytes = base64.b64decode(token_id_base64, validate=True)
    except binascii.Error:
        raise JsonableError(_("Invalid `token_id`"))

    return int.from_bytes(token_id_bytes, byteorder="big", signed=True)


def get_devices(user_profile: UserProfile) -> dict[str, DeviceInfoDict]:
    devices = Device.objects.filter(user=user_profile)

    return {
        str(device.id): {
            "push_key_id": device.push_key_id,
            "push_token_id": b64encode_token_id(device.push_token_id)
            if device.push_token_id is not None
            else None,
            "pending_push_token_id": b64encode_token_id(device.pending_push_token_id)
            if device.pending_push_token_id is not None
            else None,
            "push_token_last_updated_timestamp": datetime_to_timestamp(
                device.push_token_last_updated_timestamp
            )
            if device.push_token_last_updated_timestamp
            else None,
            "push_registration_error_code": device.push_registration_error_code,
        }
        for device in devices
    }


def check_device_id(device_id: int, user_id: int) -> Device:
    try:
        device = Device.objects.get(id=device_id, user_id=user_id)
    except Device.DoesNotExist:
        raise JsonableError(_("Invalid `device_id`"))

    return device
