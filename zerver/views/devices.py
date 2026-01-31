from django.http import HttpRequest, HttpResponse

from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models.devices import Device
from zerver.models.users import UserProfile
from zerver.tornado.django_api import send_event_on_commit


@typed_endpoint_without_parameters
def register_device(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    device = Device.objects.create(user=user_profile)
    event = dict(
        type="device",
        op="add",
        device_id=device.id,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
    return json_success(request, data={"device_id": device.id})
