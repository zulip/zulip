from django.conf import settings
from django.utils.translation import gettext as _

from zerver.actions.message_send import internal_send_stream_message
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.models import Message, Realm, UserProfile
from zerver.models.recipients import Recipient
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

    # Build reported message header
    if reported_message.recipient.type == Recipient.PERSONAL:
        report_header = _(
            "{reporting_user_mention} reported a DM sent by {reported_user_mention}."
        ).format(
            reporting_user_mention=reporting_user_mention,
            reported_user_mention=reported_user_mention,
        )
    elif reported_message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        recipient_list = get_display_recipient(reported_message.recipient)
        last_user = recipient_list.pop()
        last_user_mention = silent_mention_syntax_for_user(last_user)
        recipient_mentions: str = ", ".join(
            [silent_mention_syntax_for_user(user) for user in recipient_list]
        )
        report_header = _(
            "{reporting_user_mention} reported a DM sent by {reported_user_mention} to {recipient_mentions}, and {last_user_mention}."
        ).format(
            reporting_user_mention=reporting_user_mention,
            reported_user_mention=reported_user_mention,
            recipient_mentions=recipient_mentions,
            last_user_mention=last_user_mention,
        )
    else:
        assert reported_message.is_stream_message() is True
        topic_name = reported_message.topic_name()
        channel = reported_message.recipient.label()
        channel_message_link = f"#**{channel}>{topic_name}@{reported_message.id}**"
        report_header = _(
            "{reporting_user_mention} reported {channel_message_link} sent by {reported_user_mention}."
        ).format(
            reporting_user_mention=reporting_user_mention,
            reported_user_mention=reported_user_mention,
            channel_message_link=channel_message_link,
        )

    content = report_header

    # Build report context block
    report_context_block = _("""
- Reason: **{report_type}**
- Notes:
""").format(report_type=report_type)
    report_context_block += f"```quote\n{description}\n```"
    content += report_context_block

    # Build reported message preview block
    message_sent_by = _("**Message sent by {reported_user_mention}**").format(
        reported_user_mention=reported_user_mention
    )
    reported_message_content = truncate_content(
        reported_message.content, MAX_REPORT_MESSAGE_SNIPPET_LENGTH, "\n[message truncated]"
    )
    reported_message_preview_block = """
{fence} spoiler {message_sent_by}
{reported_message}
{fence}
""".format(
        message_sent_by=message_sent_by,
        reported_message=reported_message_content,
        fence=get_unused_fence(reported_message_content),
    )
    content += reported_message_preview_block

    internal_send_stream_message(
        sender=get_system_bot(settings.NOTIFICATION_BOT, moderation_request_channel.realm.id),
        stream=moderation_request_channel,
        topic_name=_("{fullname}'s moderation requests").format(fullname=reported_user.full_name),
        content=content,
    )
