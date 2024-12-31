from typing import Annotated

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import StringConstraints

from zerver.actions.message_send import do_send_messages, internal_prep_stream_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import access_message, get_unused_fence
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.lib.url_encoding import near_message_url
from zerver.models import Message, Realm, UserProfile
from zerver.models.users import get_system_bot

MESSAGE_REPORT_TEMPLATE = """
Reporting reason: **`{reason}`, reported by {reporting_user} who included these notes:**
{explanation}
Originally sent to: {recipient_info}
{offending_user} [said]({message_link}): {fence} quote
{offenders_message}
{fence}
"""


def send_message_report(
    user_profile: UserProfile,
    realm: Realm,
    offenders_message: Message,
    reason: str,
    explanation: str,
) -> None:
    offending_user = offenders_message.sender

    content = MESSAGE_REPORT_TEMPLATE.format(
        reason=reason,
        explanation=explanation,
        reporting_user=silent_mention_syntax_for_user(user_profile),
        offending_user=silent_mention_syntax_for_user(offending_user),
        recipient_info="",
        message_link=near_message_url(realm),
        offenders_message=offenders_message.content,
        fence=get_unused_fence(offenders_message.content),
    )

    moderation_request_channel = realm.get_moderation_request_channel()
    assert moderation_request_channel is not None

    message_report = internal_prep_stream_message(
        sender=get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id),
        stream=moderation_request_channel,
        topic_name=f"{offending_user} - {offending_user.delivery_email}",
        content=_(content),
    )
    do_send_messages([message_report])


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

    send_message_report(user_profile, user_profile.realm, offenders_message, reason, explanation)

    return json_success(request)
