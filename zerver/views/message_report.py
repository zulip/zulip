from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import StringConstraints

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.models import UserProfile
from zerver.models.realms import Realm


@typed_endpoint
def report_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    *,
    reason: Annotated[str, check_string_in_validator(Realm.REPORT_MESSAGE_REASONS)],
    explanation: Annotated[
        str, StringConstraints(max_length=Realm.MAX_REPORT_MESSAGE_EXPLANATION_LENGTH)
    ] = "",
) -> HttpResponse:
    if user_profile.realm.get_moderation_request_channel() is None:
        raise JsonableError(
            _("Moderation request channel must be specified to enable message reporting.")
        )
    if reason == "other" and explanation == "":
        raise JsonableError(_("For reason=other, an explanation must be provided."))

    if user_profile.role == UserProfile.ROLE_GUEST:
        raise JsonableError(_("You can't report this message."))

    offenders_message = access_message(user_profile, message_id)

    if offenders_message.sender == user_profile:
        raise JsonableError(_("You can't report this message."))

    # TODO: The main logic to send the reported message to `moderation_request_channel`.

    return json_success(request)
