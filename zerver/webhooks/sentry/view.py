import logging
from typing import Any, Dict, List, Optional, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import UnexpectedWebhookEventType, check_send_webhook_message
from zerver.models import UserProfile

DEPRECATED_EXCEPTION_MESSAGE_TEMPLATE = """
New [issue]({url}) (level: {level}):

``` quote
{message}
```
"""

MESSAGE_EVENT_TEMPLATE = """
**New message event:** [{title}]({web_link})
```quote
**level:** {level}
**timestamp:** {datetime}
```
"""

EXCEPTION_EVENT_TEMPLATE = """
**New exception:** [{title}]({web_link})
```quote
**level:** {level}
**timestamp:** {datetime}
**filename:** {filename}
```
"""

EXCEPTION_EVENT_TEMPLATE_WITH_TRACEBACK = EXCEPTION_EVENT_TEMPLATE + """
Traceback:
```{syntax_highlight_as}
{pre_context}---> {context_line}{post_context}\
```
"""
# Because of the \n added at the end of each context element,
# this will actually look better in the traceback.

ISSUE_CREATED_MESSAGE_TEMPLATE = """
**New issue created:** {title}
```quote
**level:** {level}
**timestamp:** {datetime}
**assignee:** {assignee}
```
"""

ISSUE_ASSIGNED_MESSAGE_TEMPLATE = """
Issue **{title}** has now been assigned to **{assignee}** by **{actor}**.
"""

ISSUE_RESOLVED_MESSAGE_TEMPLATE = """
Issue **{title}** was marked as resolved by **{actor}**.
"""

ISSUE_IGNORED_MESSAGE_TEMPLATE = """
Issue **{title}** was ignored by **{actor}**.
"""

# Maps "platform" name provided by Sentry to the Pygments lexer name
syntax_highlight_as_map = {
    "go": "go",
    "java": "java",
    "javascript": "javascript",
    "node": "javascript",
    "python": "python3",
}


def convert_lines_to_traceback_string(lines: Optional[List[str]]) -> str:
    traceback = ""
    if lines is not None:
        for line in lines:
            if (line == ""):
                traceback += "\n"
            else:
                traceback += f"     {line}\n"
    return traceback


def handle_event_payload(event: Dict[str, Any]) -> Tuple[str, str]:
    """ Handle either an exception type event or a message type event payload."""
    subject = event["title"]

    # We shouldn't support the officially deprecated Raven series of SDKs.
    if int(event["version"]) < 7:
        raise UnexpectedWebhookEventType("Sentry", "Raven SDK")

    platform_name = event["platform"]
    syntax_highlight_as = syntax_highlight_as_map.get(platform_name, "")
    if syntax_highlight_as == "":  # nocoverage
        logging.info(f"Unknown Sentry platform: {platform_name}")

    context = {
        "title": subject,
        "level": event["level"],
        "web_link": event["web_url"],
        "datetime": event["datetime"].split(".")[0].replace("T", " "),
    }

    if "exception" in event:
        # The event was triggered by a sentry.capture_exception() call
        # (in the Python Sentry SDK) or something similar.

        filename = event["metadata"].get("filename", None)

        stacktrace = None
        for value in reversed(event["exception"]["values"]):
            if "stacktrace" in value:
                stacktrace = value["stacktrace"]
                break

        if stacktrace and filename:
            exception_frame = None
            for frame in reversed(stacktrace["frames"]):
                if frame.get("filename", None) == filename:
                    exception_frame = frame
                    break

            if exception_frame and exception_frame["context_line"]:
                pre_context = convert_lines_to_traceback_string(exception_frame["pre_context"])

                context_line = exception_frame["context_line"] + "\n"
                if not context_line:
                    context_line = "\n"  # nocoverage

                post_context = convert_lines_to_traceback_string(exception_frame["post_context"])

                context.update(
                    syntax_highlight_as=syntax_highlight_as,
                    filename=filename,
                    pre_context=pre_context,
                    context_line=context_line,
                    post_context=post_context,
                )

                body = EXCEPTION_EVENT_TEMPLATE_WITH_TRACEBACK.format(**context)
                return (subject, body)

        context.update(filename=filename)  # nocoverage
        body = EXCEPTION_EVENT_TEMPLATE.format(**context)  # nocoverage
        return (subject, body)  # nocoverage

    elif "logentry" in event:
        # The event was triggered by a sentry.capture_message() call
        # (in the Python Sentry SDK) or something similar.
        body = MESSAGE_EVENT_TEMPLATE.format(**context)

    else:
        raise UnexpectedWebhookEventType("Sentry", "unknown-event type")

    return (subject, body)


def handle_issue_payload(action: str, issue: Dict[str, Any], actor: Dict[str, Any]) -> Tuple[str, str]:
    """ Handle either an issue type event. """
    subject = issue["title"]
    datetime = issue["lastSeen"].split(".")[0].replace("T", " ")

    if issue["assignedTo"]:
        if issue["assignedTo"]["type"] == "team":
            assignee = "team {}".format(issue["assignedTo"]["name"])
        else:
            assignee = issue["assignedTo"]["name"]
    else:
        assignee = "No one"

    if action == "created":
        context = {
            "title": subject,
            "level": issue["level"],
            "datetime": datetime,
            "assignee": assignee,
        }
        body = ISSUE_CREATED_MESSAGE_TEMPLATE.format(**context)

    elif action == "resolved":
        context = {
            "title": subject,
            "actor": actor["name"],
        }
        body = ISSUE_RESOLVED_MESSAGE_TEMPLATE.format(**context)

    elif action == "assigned":
        context = {
            "title": subject,
            "assignee": assignee,
            "actor": actor["name"],
        }
        body = ISSUE_ASSIGNED_MESSAGE_TEMPLATE.format(**context)

    elif action == "ignored":
        context = {
            "title": subject,
            "actor": actor["name"],
        }
        body = ISSUE_IGNORED_MESSAGE_TEMPLATE.format(**context)

    else:
        raise UnexpectedWebhookEventType("Sentry", "unknown-issue-action type")

    return (subject, body)


def handle_deprecated_payload(payload: Dict[str, Any]) -> Tuple[str, str]:
    subject = "{}".format(payload.get('project_name'))
    body = DEPRECATED_EXCEPTION_MESSAGE_TEMPLATE.format(
        level=payload['level'].upper(),
        url=payload.get('url'),
        message=payload.get('message'),
    )
    return (subject, body)


@api_key_only_webhook_view('Sentry')
@has_request_variables
def api_sentry_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any] = REQ(argument_type="body")) -> HttpResponse:
    data = payload.get("data", None)

    # We currently support two types of payloads: events and issues.
    if data:
        if "event" in data:
            subject, body = handle_event_payload(data["event"])
        elif "issue" in data:
            subject, body = handle_issue_payload(payload["action"], data["issue"], payload["actor"])
        else:
            raise UnexpectedWebhookEventType("Sentry", str(list(data.keys())))
    else:
        subject, body = handle_deprecated_payload(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()
