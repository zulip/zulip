
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import to_non_negative_int
from zerver.lib.actions import do_update_pointer
from zerver.lib.request import has_request_variables, JsonableError, REQ
from zerver.lib.response import json_success
from zerver.models import UserProfile, get_usermessage_by_message_id

def get_pointer_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success({'pointer': user_profile.pointer})

@has_request_variables
def update_pointer_backend(request: HttpRequest, user_profile: UserProfile,
                           pointer: int=REQ(converter=to_non_negative_int)) -> HttpResponse:
    if pointer <= user_profile.pointer:
        return json_success()

    if get_usermessage_by_message_id(user_profile, pointer) is None:
        raise JsonableError(_("Invalid message ID"))

    request._log_data["extra"] = "[%s]" % (pointer,)
    update_flags = (request.client.name.lower() in ['android', "zulipandroid"])
    do_update_pointer(user_profile, request.client, pointer, update_flags=update_flags)

    return json_success()
