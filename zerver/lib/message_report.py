from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.models import Message, Realm, UserProfile
from zerver.models.recipients import Recipient
from zerver.models.users import get_system_bot

MESSAGE_REPORT_TEMPLATE = """
{reporting_user} {message_sent_to}.
- Reason: **{reason}**
- Notes:
```quote
{explanation}
```
``` spoiler **Message sent by {reported_user}**
{reported_message}
```
"""

MESSAGE_REPORT_TOPIC_NAME = "{fullname}'s moderation requests"

MESSAGE_REPORT_SENT_TO_STRING = "reported a DM sent by {reported_user} to {recipients}"

# We shrink the truncate length for the reported message to ensure
# that the "notes" included by the reporting user fit within the
# limit. The extra 500 is an arbitrary buffer for all the extra
# template strings.
MAX_REPORT_MESSAGE_SNIPPET_LENGTH = (
    settings.MAX_MESSAGE_LENGTH - Realm.MAX_REPORT_MESSAGE_EXPLANATION_LENGTH - 500
)


def send_message_report(
    reporting_user: UserProfile,
    realm: Realm,
    reported_message: Message,
    reason: str,
    explanation: str,
) -> None:
    moderation_request_channel = realm.moderation_request_channel
    assert moderation_request_channel is not None

    reported_user = reported_message.sender
    reported_user_mention = silent_mention_syntax_for_user(reported_user)
    reporting_user_mention = silent_mention_syntax_for_user(reporting_user)

    if reported_message.recipient.type == Recipient.PERSONAL:
        message_sent_to = MESSAGE_REPORT_SENT_TO_STRING.format(
            recipients=f"{reporting_user_mention}",
            reported_user=reported_user_mention,
        )
    elif reported_message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        recipient_list = get_display_recipient(reported_message.recipient)
        last_user = recipient_list.pop()
        last_user_mention = f"@_**{last_user['full_name']}|{last_user['id']}**"
        recipient_mentions: str = ", ".join(
            [f"@_**{user['full_name']}|{user['id']}**" for user in recipient_list]
        )
        message_sent_to = MESSAGE_REPORT_SENT_TO_STRING.format(
            recipients=f"{recipient_mentions}, and {last_user_mention}",
            reported_user=reported_user_mention,
        )
    else:
        assert reported_message.is_stream_message() is True
        topic_name = reported_message.topic_name()
        channel = reported_message.recipient.label()
        message_sent_to = f"reported #**{channel}>{topic_name}@{reported_message.id}** sent by {reported_user_mention}"

    reported_message_content = truncate_content(
        reported_message.content, MAX_REPORT_MESSAGE_SNIPPET_LENGTH, "\n[message truncated]"
    )

    content = MESSAGE_REPORT_TEMPLATE.format(
        reason=reason,
        explanation=explanation,
        reporting_user=reporting_user_mention,
        reported_user=reported_user_mention,
        message_sent_to=message_sent_to,
        reported_message=reported_message_content,
    )

    with override_language(realm.default_language):
        internal_send_stream_message(
            sender=get_system_bot(settings.NOTIFICATION_BOT, moderation_request_channel.realm.id),
            stream=moderation_request_channel,
            topic_name=MESSAGE_REPORT_TOPIC_NAME.format(fullname=reported_user.full_name),
            content=_(content),
        )
