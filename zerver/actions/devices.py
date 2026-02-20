from zerver.models.devices import Device
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def do_register_device(user_profile: UserProfile) -> int:
    device = Device.objects.create(user=user_profile)
    event = dict(
        type="device",
        op="add",
        device_id=device.id,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
    return device.id
