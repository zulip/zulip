from django.utils.translation import gettext as _
from typing_extensions import TypedDict

from zerver.lib.exceptions import JsonableError
from zerver.models.devices import Device
from zerver.models.users import UserProfile


class DeviceInfoDict(TypedDict):
    push_key_id: int | None
    push_token_id: int | None
    pending_push_token_id: int | None
    push_registration_error_code: str | None


def get_devices(user_profile: UserProfile) -> dict[int, DeviceInfoDict]:
    devices = Device.objects.filter(user=user_profile)

    return {
        device.id: {
            "push_key_id": device.push_key_id,
            "push_token_id": device.push_token_id,
            "pending_push_token_id": device.pending_push_token_id,
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
