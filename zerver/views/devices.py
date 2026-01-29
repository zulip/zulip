from django.http import HttpRequest, HttpResponse

from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models.devices import Device
from zerver.models.users import UserProfile


@typed_endpoint_without_parameters
def register_device(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    device = Device.objects.create(user=user_profile)
    return json_success(request, data={"device_id": device.id})
