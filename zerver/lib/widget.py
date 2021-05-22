import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from zerver.lib.message import SendMessageRequest
from zerver.models import Message, SubMessage


def get_widget_data(content: str) -> Tuple[Optional[str], Optional[str]]:
    valid_widget_types = ["poll", "todo"]
    tokens = content.split(" ")

    # tokens[0] will always exist
    if tokens[0].startswith("/"):
        widget_type = tokens[0][1:]
        if widget_type in valid_widget_types:
            remaining_content = content.replace(tokens[0], "", 1).strip()
            extra_data = get_extra_data_from_widget_type(remaining_content, widget_type)
            return widget_type, extra_data

    return None, None


def get_widget_lines_of_text(lines: List[str], callback: Callable[[str], None]) -> None:
    for line in lines:
        # If someone is using the list syntax, we remove it
        # before adding an option.
        stripped_line = re.sub(r"(\s*[-*]?\s*)", "", line.strip(), 1)
        if len(stripped_line) > 0:
            callback(stripped_line)


def get_extra_data_from_widget_type(content: str, widget_type: Optional[str]) -> Any:
    if widget_type == "poll":
        # This is used to extract the question from the poll command.
        # The command '/poll question' will pre-set the question in the poll
        lines = content.splitlines()
        question = ""
        options = []
        if lines and lines[0]:
            question = lines.pop(0).strip()

        def append_option(option: str) -> None:
            options.append(option)

        get_widget_lines_of_text(lines, append_option)
        poll_extra_data = {
            "question": question,
            "options": options,
        }
        return poll_extra_data
    if widget_type == "todo":
        todos: List[Dict[str, object]] = []
        lines = content.splitlines()

        def append_todo(todo_string: str) -> None:
            completed = False
            if todo_string.startswith("[x] "):
                todo_string = todo_string[4:]  # strip the "[x] "
                completed = True
            if todo_string.startswith("[ ] "):
                todo_string = todo_string[4:]  # strip the "[ ] "
                completed = False
            if todo_string.startswith("[] "):
                todo_string = todo_string[3:]  # strip the "[] "
                completed = False
            todo_string_split = todo_string.split(" - ", 1)
            task = todo_string_split[0].strip()
            if task:
                description = ""
                if len(todo_string_split) > 1:
                    description = todo_string_split[1].strip()
                todo = {
                    "task": task,
                    "description": description,
                    "completed": completed,
                }
                todos.append(todo.copy())

        get_widget_lines_of_text(lines, append_todo)
        todo_extra_data = {
            "todos": todos,
        }
        return todo_extra_data


def do_widget_post_save_actions(send_request: SendMessageRequest) -> None:
    """
    This code works with the web app; mobile and other
    clients should also start supporting this soon.
    """
    message_content = send_request.message.content
    sender_id = send_request.message.sender_id
    message_id = send_request.message.id

    widget_type = None
    extra_data = None

    widget_type, extra_data = get_widget_data(message_content)
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


def is_widget_message(message: Message) -> bool:
    # Right now all messages that are widgetized use submessage, and vice versa.
    return message.submessage_set.exists()
