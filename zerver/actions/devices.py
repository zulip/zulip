from zerver.lib.devices import check_device_id
from zerver.lib.event_types import DeviceAddEvent, DeviceRemoveEvent
from zerver.models.devices import Device
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def do_register_device(user_profile: UserProfile) -> int:
    device = Device.objects.create(user=user_profile)
    event = DeviceAddEvent(device_id=device.id)
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
    return device.id


def do_remove_device(user_profile: UserProfile, device_id: int) -> None:
    device = check_device_id(device_id, user_profile.id)
    device.delete()

    event = DeviceRemoveEvent(device_id=device_id)
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
