import json
import re
from typing import Any

from zerver.lib.message import SendMessageRequest
from zerver.lib.queue import queue_event_on_commit
from zerver.models import Message, SubMessage


def get_widget_data(content: str, realm_id: int | None = None) -> tuple[str | None, Any]:
    """
    Parse message content for built-in widget types (poll, todo).

    Bot slash commands are NOT parsed from plain text messages - they require
    the command composer UI which sends the command via /json/bot_commands/invoke.
    This ensures users can type /something as regular text without accidentally
    invoking a bot command.
    """
    valid_widget_types = ["poll", "todo"]
    tokens = re.split(r"\s+|\n+", content)

    # tokens[0] will always exist
    if tokens[0].startswith("/"):
        widget_type = tokens[0].removeprefix("/")
        if widget_type in valid_widget_types:
            remaining_content = content.replace(tokens[0], "", 1)
            extra_data = get_extra_data_from_widget_type(remaining_content, widget_type)
            return widget_type, extra_data

        # NOTE: Bot commands are NOT parsed from plain text. Users must use the
        # command composer UI (which uses /json/bot_commands/invoke) to invoke
        # bot commands. This prevents accidental command invocation when typing
        # /something as regular text.

    return None, None


def parse_poll_extra_data(content: str) -> Any:
    # This is used to extract the question from the poll command.
    # The command '/poll question' will pre-set the question in the poll
    lines = content.splitlines()
    question = ""
    options = []
    if lines and lines[0]:
        question = lines.pop(0).strip()
    for line in lines:
        # If someone is using the list syntax, we remove it
        # before adding an option.
        option = re.sub(r"(\s*[-*]?\s*)", "", line.strip(), count=1)
        if len(option) > 0:
            options.append(option)
    extra_data = {
        "question": question,
        "options": options,
    }
    return extra_data


def parse_todo_extra_data(content: str) -> Any:
    # This is used to extract the task list title from the todo command.
    # The command '/todo Title' will pre-set the task list title
    lines = content.splitlines()
    task_list_title = ""
    if lines and lines[0]:
        task_list_title = lines.pop(0).strip()
    tasks = []
    for line in lines:
        # If someone is using the list syntax, we remove it
        # before adding a task.
        task_data = re.sub(r"(\s*[-*]?\s*)", "", line.strip(), count=1)
        if len(task_data) > 0:
            # a task and its description (optional) are separated
            # by the (first) `: ` substring
            task_data_array = task_data.split(": ", 1)
            tasks.append(
                {
                    "task": task_data_array[0].strip(),
                    "desc": task_data_array[1].strip() if len(task_data_array) > 1 else "",
                }
            )
    extra_data = {
        "task_list_title": task_list_title,
        "tasks": tasks,
    }
    return extra_data


def get_extra_data_from_widget_type(content: str, widget_type: str | None) -> Any:
    if widget_type == "poll":
        return parse_poll_extra_data(content)
    else:
        return parse_todo_extra_data(content)


def do_widget_post_save_actions(send_request: SendMessageRequest) -> None:
    """
    This code works with the web app; mobile and other
    clients should also start supporting this soon.
    """
    message_content = send_request.message.content
    sender_id = send_request.message.sender_id
    message_id = send_request.message.id
    realm_id = send_request.message.realm_id

    widget_type = None
    extra_data = None

    widget_type, extra_data = get_widget_data(message_content, realm_id)
    widget_content = send_request.widget_content
    if widget_content is not None:
        # Note that we validate this data in check_message,
        # so we can trust it here.
        widget_type = widget_content["widget_type"]
        extra_data = widget_content["extra_data"]

    if widget_type:
        content = dict(
            widget_type=widget_type,
            extra_data=extra_data,
        )
        submessage = SubMessage(
            sender_id=sender_id,
            message_id=message_id,
            msg_type="widget",
            content=json.dumps(content),
        )
        submessage.save()
        send_request.submessages = SubMessage.get_raw_db_rows([message_id])

        # For bot command invocations, queue a notification to the bot
        if widget_type == "command_invocation" and extra_data:
            queue_bot_command_notification(
                send_request.message,
                extra_data,
            )


def queue_bot_command_notification(
    message: Message,
    extra_data: dict[str, Any],
) -> None:
    """Queue a command invocation event for the bot to process."""
    from zerver.models import Recipient, Stream, UserProfile

    bot_id = extra_data.get("bot_id")
    if not bot_id:
        return

    # Get sender info for user context
    try:
        sender = UserProfile.objects.get(id=message.sender_id)
        user_data = {
            "id": sender.id,
            "email": sender.delivery_email,
            "full_name": sender.full_name,
        }
    except UserProfile.DoesNotExist:
        user_data = {}

    # Build context with stream/topic info if applicable
    context: dict[str, Any] = {
        "realm_id": message.realm_id,
    }

    if message.recipient.type == Recipient.STREAM:
        context["stream_id"] = message.recipient.type_id
        context["topic"] = message.topic_name()
        # Also try to get stream name
        try:
            stream = Stream.objects.get(id=message.recipient.type_id)
            context["stream_name"] = stream.name
        except Stream.DoesNotExist:
            pass

    event = {
        "type": "command_invocation",
        "bot_user_id": bot_id,
        "user_profile_id": message.sender_id,
        "message_id": message.id,
        "command": extra_data.get("command_name", ""),
        "arguments": extra_data.get("arguments", {}),
        "context": context,
        "user": user_data,
    }

    # Queue for webhook delivery to the bot
    queue_event_on_commit("bot_interactions", event)


def get_widget_type(*, message_id: int) -> str | None:
    submessage = (
        SubMessage.objects.filter(
            message_id=message_id,
            msg_type="widget",
        )
        .only("content")
        .first()
    )

    if submessage is None:
        return None

    try:
        data = json.loads(submessage.content)
    except Exception:
        return None

    try:
        return data["widget_type"]
    except Exception:
        return None


def is_widget_message(message: Message) -> bool:
    # Right now all messages that are widgetized use submessage, and vice versa.
    return message.submessage_set.exists()
