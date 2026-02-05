from django.conf import settings
from django.utils.translation import gettext as _

from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import is_1_to_1_message, truncate_content
from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.topic_link_util import get_message_link_syntax
from zerver.lib.url_encoding import pm_message_url
from zerver.models import Message, Realm, UserProfile
from zerver.models.recipients import Recipient
from zerver.models.streams import StreamTopicsPolicyEnum
from zerver.models.users import get_system_bot

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
    report_type: str,
    description: str,
) -> None:
    moderation_request_channel = realm.moderation_request_channel
    assert moderation_request_channel is not None

    reported_user = reported_message.sender
    reported_user_mention = silent_mention_syntax_for_user(reported_user)
    reporting_user_mention = silent_mention_syntax_for_user(reporting_user)
    report_reason = Realm.REPORT_MESSAGE_REASONS[report_type]
    reported_message_date_sent = datetime_to_global_time(reported_message.date_sent)

    # Build reported message header
    if is_1_to_1_message(reported_message):
        if reported_user != reporting_user:
            report_header = _(
                "{reporting_user_mention} reported a direct message sent by {reported_user_mention} at {reported_message_date_sent}."
            ).format(
                reporting_user_mention=reporting_user_mention,
                reported_user_mention=reported_user_mention,
                reported_message_date_sent=reported_message_date_sent,
            )
        else:
            # Clearly mention the direct message recipient if someone is
            # reporting their own message in a 1-on-1 direct message.
            if reported_message.recipient.type_id != reporting_user.id:
                recipient_user = next(
                    silent_mention_syntax_for_user(user)
                    for user in get_display_recipient(reported_message.recipient)
                    if user["id"] != reporting_user.id
                )
            else:
                recipient_user = reporting_user_mention
            report_header = _(
                "{reporting_user_mention} reported a direct message sent by {reported_user_mention} to {recipient_user} at {reported_message_date_sent}."
            ).format(
                reporting_user_mention=reporting_user_mention,
                reported_user_mention=reported_user_mention,
                recipient_user=recipient_user,
                reported_message_date_sent=reported_message_date_sent,
            )
    elif reported_message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        recipient_list = sorted(
            [
                silent_mention_syntax_for_user(user)
                for user in get_display_recipient(reported_message.recipient)
                if user["id"] is not reported_user.id
            ]
        )
        last_recipient_user = recipient_list.pop()
        recipient_users: str = ", ".join(recipient_list)
        if len(recipient_list) > 1:
            recipient_users += ","
        report_header = _(
            "{reporting_user_mention} reported a direct message sent by {reported_user_mention} to {recipient_users} and {last_recipient_user} at {reported_message_date_sent}."
        ).format(
            reporting_user_mention=reporting_user_mention,
            reported_user_mention=reported_user_mention,
            recipient_users=recipient_users,
            last_recipient_user=last_recipient_user,
            reported_message_date_sent=reported_message_date_sent,
        )
    else:
        assert reported_message.is_channel_message is True
        topic_name = reported_message.topic_name()
        channel_id = reported_message.recipient.type_id
        channel_name = reported_message.recipient.label()
        channel_message_link = get_message_link_syntax(
            channel_id,
            channel_name,
            topic_name,
            reported_message.id,
        )
        report_header = _(
            "{reporting_user_mention} reported a message sent by {reported_user_mention} at {reported_message_date_sent}."
        ).format(
            reporting_user_mention=reporting_user_mention,
            reported_user_mention=reported_user_mention,
            reported_message_date_sent=reported_message_date_sent,
        )

    content = report_header

    # Build report context and message preview block
    if reported_message.is_channel_message:
        original_message_string = _("Original message at {channel_message_link}").format(
            channel_message_link=channel_message_link
        )
    else:
        direct_message_link = pm_message_url(
            realm,
            dict(
                id=reported_message.id,
                display_recipient=get_display_recipient(reported_message.recipient),
            ),
        )
        original_message_string = _("[Original message]({direct_message_link})").format(
            direct_message_link=direct_message_link
        )

    reported_message_content = truncate_content(
        reported_message.content, MAX_REPORT_MESSAGE_SNIPPET_LENGTH, "\n[message truncated]"
    )
    reported_message_preview_block = """
```quote
**{report_reason}**. {description}
```

{fence} spoiler {original_message_string}
{reported_message}
{fence}
""".format(
        report_reason=report_reason,
        description=description,
        original_message_string=original_message_string,
        reported_message=reported_message_content,
        fence=get_unused_fence(reported_message_content),
    )
    content += reported_message_preview_block

    topic_name = _("{fullname} moderation").format(fullname=reported_user.full_name)
    if moderation_request_channel.topics_policy == StreamTopicsPolicyEnum.empty_topic_only.value:
        topic_name = ""

    internal_send_stream_message(
        sender=get_system_bot(settings.NOTIFICATION_BOT, moderation_request_channel.realm.id),
        stream=moderation_request_channel,
        topic_name=topic_name,
        content=content,
        acting_user=reporting_user,
    )
