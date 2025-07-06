from django.conf import settings
from django.utils.translation import gettext as _

from zerver.lib.exceptions import ResourceNotFoundError
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.lib.message_cache import MessageDict
from zerver.lib.topic_link_util import get_message_link_syntax
from zerver.lib.url_encoding import message_link_url
from zerver.models import Message, Stream, UserProfile
from zerver.models.scheduled_jobs import ScheduledMessage


def get_reminder_formatted_content(message: Message, current_user: UserProfile) -> str:
    if message.is_stream_message():
        # We don't need to check access here since we already have the message
        # whose access has already been checked by the caller.
        stream = Stream.objects.get(
            id=message.recipient.type_id,
            realm=current_user.realm,
        )
        content = _("You requested a reminder for {message_pretty_link}.").format(
            message_pretty_link=get_message_link_syntax(
                stream_id=stream.id,
                stream_name=stream.name,
                topic_name=message.topic_name(),
                message_id=message.id,
            )
        )
    else:
        content = _("You requested a reminder for the following direct message.")

    # Format the message content as a quote.
    user_silent_mention = silent_mention_syntax_for_user(message.sender)
    conversation_url = message_link_url(current_user.realm, MessageDict.wide_dict(message))
    content += "\n\n"
    if message.content.startswith("/poll"):
        content += _("{user_silent_mention} [sent]({conversation_url}) a poll.").format(
            user_silent_mention=user_silent_mention,
            conversation_url=conversation_url,
        )
    elif message.content.startswith("/todo"):
        content += _("{user_silent_mention} [sent]({conversation_url}) a todo list.").format(
            user_silent_mention=user_silent_mention,
            conversation_url=conversation_url,
        )
    else:
        content += _("{user_silent_mention} [said]({conversation_url}):").format(
            user_silent_mention=user_silent_mention,
            conversation_url=conversation_url,
        )
        content += "\n"
        fence = get_unused_fence(content)
        quoted_message = "{fence}quote\n{msg_content}\n{fence}"
        content += quoted_message
        length_without_message_content = len(content.format(fence=fence, msg_content=""))
        max_length = settings.MAX_MESSAGE_LENGTH - length_without_message_content
        msg_content = truncate_content(message.content, max_length, "\n[message truncated]")
        content = content.format(
            fence=fence,
            msg_content=msg_content,
        )
    return content


def access_reminder(user_profile: UserProfile, reminder_id: int) -> ScheduledMessage:
    try:
        return ScheduledMessage.objects.get(
            id=reminder_id, sender=user_profile, delivery_type=ScheduledMessage.REMIND
        )
    except ScheduledMessage.DoesNotExist:
        raise ResourceNotFoundError(_("Reminder does not exist"))
