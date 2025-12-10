from django.conf import settings
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import truncate_content
from zerver.lib.message_cache import MessageDict
from zerver.lib.topic_link_util import get_message_link_syntax
from zerver.lib.url_encoding import message_link_url
from zerver.models import Message, Stream, UserProfile
from zerver.models.scheduled_jobs import ScheduledMessage
from zerver.tornado.django_api import send_event_on_commit


def normalize_note_text(body: str) -> str:
    # Similar to zerver.lib.message.normalize_body
    body = body.rstrip().lstrip("\n")

    if len(body) > settings.MAX_REMINDER_NOTE_LENGTH:
        raise JsonableError(
            _("Maximum reminder note length: {max_length} characters").format(
                max_length=settings.MAX_REMINDER_NOTE_LENGTH
            )
        )

    return body


def get_reminder_formatted_content(
    message: Message, current_user: UserProfile, note: str | None = None
) -> str:
    if note:
        note = normalize_note_text(note)

    if message.is_channel_message:
        # We don't need to check access here since we already have the message
        # whose access has already been checked by the caller.
        stream = Stream.objects.get(
            id=message.recipient.type_id,
            realm=current_user.realm,
        )
        message_pretty_link = get_message_link_syntax(
            stream_id=stream.id,
            stream_name=stream.name,
            topic_name=message.topic_name(),
            message_id=message.id,
        )
        if note:
            content = _(
                "You requested a reminder for {message_pretty_link}. Note:\n > {note}"
            ).format(
                message_pretty_link=message_pretty_link,
                note=note,
            )
        else:
            content = _("You requested a reminder for {message_pretty_link}.").format(
                message_pretty_link=message_pretty_link,
            )
    else:
        if note:
            content = _(
                "You requested a reminder for the following direct message. Note:\n > {note}"
            ).format(
                note=note,
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
        length_without_message_content = len(
            content + quoted_message.format(fence=fence, msg_content="")
        )
        max_length = settings.MAX_MESSAGE_LENGTH - length_without_message_content
        msg_content = truncate_content(message.content, max_length, "\n[message truncated]")
        content += quoted_message.format(
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


def notify_remove_reminder(user_profile: UserProfile, reminder_id: int) -> None:
    event = {
        "type": "reminders",
        "op": "remove",
        "reminder_id": reminder_id,
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
