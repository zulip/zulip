import re
from typing import Optional

from django.conf import settings
from django.utils.translation import gettext as _

from zerver.actions.message_send import internal_send_private_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.url_encoding import huddle_narrow_url, personal_narrow_url, topic_narrow_url
from zerver.models import Message, Stream, UserProfile, get_display_recipient, get_system_bot


# This function is similar to one used in fenced_code.ts
def get_unused_fence(content: str) -> str:
    # Define the regular expression pattern to match ``` fences
    fence_length_re = re.compile(r"^ {0,3}(`{3,})", re.MULTILINE)

    # Initialize the length variable to 3, corresponding to default fence length
    length = 3
    matches = fence_length_re.findall(content)
    for match in matches:
        length = max(length, len(match) + 1)

    return "`" * length


def by_conversation_and_time_url(message: Message, current_user: UserProfile) -> str:
    if message.is_stream_message():
        stream_id = message.recipient.type_id
        narrow_link = topic_narrow_url(
            realm=message.sender.realm,
            stream=Stream.objects.get(id=stream_id),
            topic=message.topic_name(),
        )
    elif message.recipient.type == message.recipient.PERSONAL:
        narrow_link = personal_narrow_url(
            realm=message.sender.realm,
            sender=message.sender,
        )
    else:
        narrow_link = huddle_narrow_url(
            user=current_user,
            display_recipient=get_display_recipient(message.recipient),
        )

    return f"{narrow_link}/near/{message.id}"


def get_reminder_formatted_content(
    message: Message, current_user: UserProfile, stream: Optional[Stream]
) -> str:
    if message.is_stream_message():
        assert stream is not None
        narrow_link = topic_narrow_url(
            realm=message.sender.realm,
            stream=stream,
            topic=message.topic_name(),
        )
        content = _(
            "You requested a reminder for the following message sent to [{stream_name} > {topic_name}]({narrow_link})."
        ).format(
            stream_name=stream.name,
            topic_name=message.topic_name(),
            narrow_link=narrow_link,
        )
    else:
        content = _("You requested a reminder for the following private message.")

    # Format the message content as a quote.
    content += "\n\n"
    content += _("@_**{sender_full_name}|{sender_id}** [said]({conversation_url}):").format(
        sender_full_name=message.sender.full_name,
        sender_id=message.sender.id,
        conversation_url=by_conversation_and_time_url(message, current_user),
    )
    content += "\n"
    fence = get_unused_fence(content)
    quoted_message = f"{fence}quote\n{message.content}\n{fence}"
    content += quoted_message
    return content


def access_message_for_reminder(current_user: UserProfile, message_id: int) -> Message:
    try:
        message, ignored_user_message = access_message(current_user, message_id)
    except JsonableError as error:
        internal_send_private_message(
            get_system_bot(settings.NOTIFICATION_BOT, current_user.realm.id),
            current_user,
            _(
                "You asked for a reminder about a [message with ID {message_id}]({message_link}), but either the message has been deleted or you no longer have access to the message."
            ).format(
                message_id=message_id,
                # This is a permalink to the message, so if the user
                # gains access to the message again, it can be used to locate it.
                message_link=f"{current_user.realm.uri}/#narrow/near/{message_id}",
            ),
        )
        raise error

    return message
