from django.http import HttpRequest, HttpResponse

from zerver.actions.devices import do_register_device
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models.users import UserProfile


@typed_endpoint_without_parameters
def register_device(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    device_id = do_register_device(user_profile)
    return json_success(request, data={"device_id": device_id})
