from typing import Annotated

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from pydantic import StringConstraints

from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.models import Message, Realm, UserProfile
from zerver.models.recipients import Recipient
from zerver.models.users import get_system_bot

MESSAGE_REPORT_TEMPLATE = """
{reporting_user} reported: {message_sent_to}
``` spoiler Message sent by {reported_user}
{reported_message}
```
- Reason: {reason}
- Explanation: {explanation}

"""

MESSAGE_REPORT_TOPIC_NAME = "User ({user_id}) reports"


def send_message_report(
    user_profile: UserProfile,
    realm: Realm,
    reported_message: Message,
    reason: str,
    explanation: str,
) -> None:
    reported_user = reported_message.sender

    if reported_message.recipient.type in {
        Recipient.PERSONAL,
        Recipient.DIRECT_MESSAGE_GROUP,
    }:
        recipient_list = get_display_recipient(reported_message.recipient)
        recipient_mentions = [f"@_**{user['full_name']}|{user['id']}**" for user in recipient_list]
        if reported_message.recipient.type == Recipient.PERSONAL:
            recipient_mentions.append(silent_mention_syntax_for_user(reported_user))
        message_sent_to = f"a private chat with between {', '.join(recipient_mentions)}"
    else:
        assert reported_message.is_stream_message() is True
        topic_name = reported_message.topic_name()
        channel = reported_message.recipient.label()
        message_sent_to = f"#**{channel}>{topic_name}@{reported_message.id}**"

    content = MESSAGE_REPORT_TEMPLATE.format(
        reason=reason,
        explanation=explanation,
        reporting_user=silent_mention_syntax_for_user(user_profile),
        reported_user=silent_mention_syntax_for_user(reported_user),
        message_sent_to=message_sent_to,
        reported_message=reported_message.content,
    )

    moderation_request_channel = realm.get_moderation_request_channel()
    assert moderation_request_channel is not None
    with override_language(realm.default_language):
        internal_send_stream_message(
            sender=get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id),
            stream=moderation_request_channel,
            topic_name=MESSAGE_REPORT_TOPIC_NAME.format(
                fullname=reported_user.full_name, user_id=reported_user.id
            ),
            content=_(content),
        )


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

    reported_message = access_message(user_profile, message_id)

    send_message_report(user_profile, user_profile.realm, reported_message, reason, explanation)

    return json_success(request)
