import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from zerver.lib.exceptions import MarkdownRenderingError
from zerver.lib.message import SendMessageRequest
from zerver.models import Message, Realm, SubMessage


@dataclass
class PollData:
    question: str
    options: list[str]
    rendered_question_html: str = ""
    rendered_options_html: list[str] = field(default_factory=list)


@dataclass
class TodoTaskData:
    task: str
    desc: str


@dataclass
class TodoData:
    task_list_title: str
    tasks: list[TodoTaskData]


def get_widget_data(content: str) -> tuple[str | None, Any]:
    valid_widget_types = ["poll", "todo"]
    tokens = re.split(r"\s+|\n+", content)

    # tokens[0] will always exist
    if tokens[0].startswith("/"):
        widget_type = tokens[0].removeprefix("/")
        if widget_type in valid_widget_types:
            remaining_content = content.replace(tokens[0], "", 1)
            extra_data = get_extra_data_from_widget_type(remaining_content, widget_type)
            return widget_type, asdict(extra_data)

    return None, None


def parse_poll_extra_data(content: str) -> PollData:
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
    return PollData(question=question, options=options)


def parse_todo_extra_data(content: str) -> TodoData:
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
                TodoTaskData(
                    task=task_data_array[0].strip(),
                    desc=task_data_array[1].strip() if len(task_data_array) > 1 else "",
                )
            )
    return TodoData(task_list_title=task_list_title, tasks=tasks)


def get_extra_data_from_widget_type(content: str, widget_type: str | None) -> PollData | TodoData:
    if widget_type == "poll":
        return parse_poll_extra_data(content)
    else:
        return parse_todo_extra_data(content)


def render_poll_extra_data(
    extra_data: dict[str, Any], message_realm: Realm | None
) -> dict[str, Any]:
    """Add rendered HTML fields to poll extra_data, preserving raw text."""
    from zerver.lib.markdown import markdown_convert_inline

    question = extra_data.get("question", "")
    options = extra_data.get("options", [])

    def safe_render(text: str) -> str:
        try:
            return markdown_convert_inline(text, message_realm)
        except MarkdownRenderingError:
            return ""

    rendered_question_html = safe_render(question) if question else ""
    rendered_options_html = [safe_render(option) for option in options]

    return {
        **extra_data,
        "rendered_question_html": rendered_question_html,
        "rendered_options_html": rendered_options_html,
    }


def render_poll_submessage_content(content: str, message_realm: Realm | None) -> str:
    """Render inline markdown for a poll submessage (new_option/question events).

    Returns the modified JSON content string with rendered fields added.
    The original raw text fields are preserved.
    """
    from zerver.lib.markdown import markdown_convert_inline

    try:
        data = json.loads(content)
    except Exception:
        return content

    if not isinstance(data, dict):
        return content

    msg_type = data.get("type")
    try:
        if msg_type == "new_option":
            option = data.get("option", "")
            if option:
                data["rendered_option_html"] = markdown_convert_inline(option, message_realm)
        elif msg_type == "question":
            question = data.get("question", "")
            if question:
                data["rendered_question_html"] = markdown_convert_inline(question, message_realm)
    except MarkdownRenderingError:
        # Rendering is an enhancement; fall back to the unrendered content
        # rather than failing the submessage request with a 500.
        return content

    return json.dumps(data)


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
        if widget_type == "poll":
            message_realm = send_request.message.get_realm()
            extra_data = render_poll_extra_data(extra_data, message_realm)

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
