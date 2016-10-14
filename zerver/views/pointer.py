from __future__ import absolute_import

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from six import text_type

from zerver.decorator import to_non_negative_int
from zerver.lib.actions import do_update_pointer, do_deactivate_user
from zerver.lib.request import has_request_variables, JsonableError, REQ
from zerver.lib.response import json_success
from zerver.lib.utils import statsd, generate_random_token
from zerver.models import UserProfile, Message, UserMessage

def get_pointer_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return json_success({'pointer': user_profile.pointer})

@has_request_variables
def update_pointer_backend(request, user_profile,
                           pointer=REQ(converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    if pointer <= user_profile.pointer:
        return json_success()

    try:
        UserMessage.objects.get(
            user_profile=user_profile,
            message__id=pointer
        )
    except UserMessage.DoesNotExist:
        raise JsonableError(_("Invalid message ID"))

    request._log_data["extra"] = "[%s]" % (pointer,)
    update_flags = (request.client.name.lower() in ['android', "zulipandroid"])
    do_update_pointer(user_profile, pointer, update_flags=update_flags)

    return json_success()

def generate_client_id():
    # type: () -> text_type
    return generate_random_token(32)

def get_profile_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    result = dict(pointer        = user_profile.pointer,
                  client_id      = generate_client_id(),
                  max_message_id = -1)

    messages = Message.objects.filter(usermessage__user_profile=user_profile).order_by('-id')[:1]
    if messages:
        result['max_message_id'] = messages[0].id

    return json_success(result)

def deactivate_user_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return _deactivate_user_profile_backend(request, user_profile)

def _deactivate_user_profile_backend(request, target):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    do_deactivate_user(target)
    return json_success({})
