import orjson
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.submessage import do_add_submessage, verify_submessage_sender
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_int, validate_poll_data, validate_todo_data
from zerver.lib.widget import get_widget_type
from zerver.models import UserProfile


# transaction.atomic is required since we use FOR UPDATE queries in access_message.
@transaction.atomic
@has_request_variables
def process_submessage(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int = REQ(json_validator=check_int),
    msg_type: str = REQ(),
    content: str = REQ(),
) -> HttpResponse:
    message = access_message(user_profile, message_id, lock_message=True)

    verify_submessage_sender(
        message_id=message.id,
        message_sender_id=message.sender_id,
        submessage_sender_id=user_profile.id,
    )

    try:
        widget_data = orjson.loads(content)
    except orjson.JSONDecodeError:
        raise JsonableError(_("Invalid json for submessage"))

    widget_type = get_widget_type(message_id=message.id)

    is_widget_author = message.sender_id == user_profile.id

    if widget_type == "poll":
        try:
            validate_poll_data(poll_data=widget_data, is_widget_author=is_widget_author)
        except ValidationError as error:
            raise JsonableError(error.message)

    if widget_type == "todo":
        try:
            validate_todo_data(todo_data=widget_data, is_widget_author=is_widget_author)
        except ValidationError as error:
            raise JsonableError(error.message)

    do_add_submessage(
        realm=user_profile.realm,
        sender_id=user_profile.id,
        message_id=message.id,
        msg_type=msg_type,
        content=content,
    )
    return json_success(request)
