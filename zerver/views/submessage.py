import ujson

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import (
    has_request_variables,
    REQ,
)
from zerver.lib.actions import do_add_submessage
from zerver.lib.message import access_message
from zerver.lib.validator import check_int
from zerver.lib.response import (
    json_error,
    json_success
)
from zerver.models import UserProfile

@has_request_variables
def process_submessage(request: HttpRequest,
                       user_profile: UserProfile,
                       message_id: int=REQ(validator=check_int),
                       msg_type: str=REQ(),
                       content: str=REQ(),
                       ) -> HttpResponse:
    message, user_message = access_message(user_profile, message_id)

    try:
        ujson.loads(content)
    except Exception:
        return json_error(_("Invalid json for submessage"))

    do_add_submessage(
        realm=user_profile.realm,
        sender_id=user_profile.id,
        message_id=message.id,
        msg_type=msg_type,
        content=content,
    )
    return json_success()
