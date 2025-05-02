from django.conf import settings
from django.utils.translation import gettext as _

from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.lib.message_cache import MessageDict
from zerver.lib.url_encoding import near_message_url, topic_narrow_url
from zerver.models import Message, Stream, UserProfile


def get_reminder_formatted_content(message: Message, current_user: UserProfile) -> str:
    if message.is_stream_message():
        # We don't need to check access here since we already have the message
        # whose access has already been checked by the caller.
        stream = Stream.objects.get(
            id=message.recipient.type_id,
            realm=current_user.realm,
        )
        narrow_link = topic_narrow_url(
            realm=current_user.realm,
            stream=stream,
            topic_name=message.topic_name(),
        )
        content = _(
            "You requested a reminder for the following message sent to [{stream_name} > {topic_name}]({narrow_link})."
        ).format(
            stream_name=stream.name,
            topic_name=message.topic_name(),
            narrow_link=narrow_link,
        )
    else:
        content = _("You requested a reminder for the following direct message.")

    # Format the message content as a quote.
    content += "\n\n"
    content += _("{user_silent_mention} [said]({conversation_url}):").format(
        user_silent_mention=silent_mention_syntax_for_user(message.sender),
        conversation_url=near_message_url(current_user.realm, MessageDict.wide_dict(message)),
    )
    content += "\n"
    fence = get_unused_fence(content)
    quoted_message = "{fence}quote\n{msg_content}\n{fence}"
    content += quoted_message
    length_without_message_content = len(content.format(fence=fence, msg_content=""))
    max_length = settings.MAX_MESSAGE_LENGTH - length_without_message_content
    msg_content = truncate_content(message.content, max_length, "\n[message truncated]")
    return content.format(
        fence=fence,
        msg_content=msg_content,
    )
