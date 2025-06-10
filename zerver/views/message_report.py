from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from pydantic import StringConstraints

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.message_report import send_message_report
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.models import Realm, UserProfile


@typed_endpoint
def report_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    *,
    report_type: Annotated[str, check_string_in_validator(Realm.REPORT_MESSAGE_REASONS)],
    description: Annotated[
        str, StringConstraints(max_length=Realm.MAX_REPORT_MESSAGE_EXPLANATION_LENGTH)
    ] = "",
) -> HttpResponse:
    if report_type == "other" and description == "":
        raise JsonableError(_("An explanation is required."))

    if user_profile.realm.moderation_request_channel is None:
        raise JsonableError(_("Message reporting is not enabled in this organization."))

    reported_message = access_message(user_profile, message_id, is_modifying_message=False)
    with override_language(user_profile.realm.default_language):
        send_message_report(
            user_profile,
            user_profile.realm,
            reported_message,
            report_type,
            description,
        )

    return json_success(request)
