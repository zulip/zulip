import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
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

EXCEPTION_EVENT_TEMPLATE_WITH_TRACEBACK = (
    EXCEPTION_EVENT_TEMPLATE
    + """
Traceback:
```{syntax_highlight_as}
{pre_context}---> {context_line}{post_context}\
```
"""
)
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
    "ruby": "ruby",
}


def is_sample_event(event: Dict[str, Any]) -> bool:
    # This is just a heuristic to detect the sample event, this should
    # not be used for making important behavior decisions.
    title = event.get("title", "")
    if title == "This is an example Python exception":
        return True
    return False


def convert_lines_to_traceback_string(lines: Optional[List[str]]) -> str:
    traceback = ""
    if lines is not None:
        for line in lines:
            if line == "":
                traceback += "\n"
            else:
                traceback += f"     {line}\n"
    return traceback


def handle_event_payload(event: Dict[str, Any]) -> Tuple[str, str]:
    """Handle either an exception type event or a message type event payload."""

    topic = event["title"]
    platform_name = event["platform"]
    syntax_highlight_as = syntax_highlight_as_map.get(platform_name, "")
    if syntax_highlight_as == "":  # nocoverage
        logging.info("Unknown Sentry platform: %s", platform_name)

    # We shouldn't support the officially deprecated Raven series of
    # Python SDKs.
    if platform_name == "python" and int(event["version"]) < 7 and not is_sample_event(event):
        # The sample event is still an old "version" -- accept it even
        # though we don't accept events from the old Python SDK.
        raise UnsupportedWebhookEventTypeError("Raven SDK")
    context = {
        "title": topic,
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

            if (
                exception_frame
                and "context_line" in exception_frame
                and exception_frame["context_line"] is not None
            ):
                pre_context = convert_lines_to_traceback_string(
                    exception_frame.get("pre_context", None)
                )
                context_line = exception_frame["context_line"] + "\n"
                post_context = convert_lines_to_traceback_string(
                    exception_frame.get("post_context", None)
                )

                context.update(
                    syntax_highlight_as=syntax_highlight_as,
                    filename=filename,
                    pre_context=pre_context,
                    context_line=context_line,
                    post_context=post_context,
                )

                body = EXCEPTION_EVENT_TEMPLATE_WITH_TRACEBACK.format(**context)
                return (topic, body)

        context.update(filename=filename)  # nocoverage
        body = EXCEPTION_EVENT_TEMPLATE.format(**context)  # nocoverage
        return (topic, body)  # nocoverage

    elif "logentry" in event:
        # The event was triggered by a sentry.capture_message() call
        # (in the Python Sentry SDK) or something similar.
        body = MESSAGE_EVENT_TEMPLATE.format(**context)

    else:
        raise UnsupportedWebhookEventTypeError("unknown-event type")

    return (topic, body)


def handle_issue_payload(
    action: str, issue: Dict[str, Any], actor: Dict[str, Any]
) -> Tuple[str, str]:
    """Handle either an issue type event."""
    topic = issue["title"]
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
            "title": topic,
            "level": issue["level"],
            "datetime": datetime,
            "assignee": assignee,
        }
        body = ISSUE_CREATED_MESSAGE_TEMPLATE.format(**context)

    elif action == "resolved":
        context = {
            "title": topic,
            "actor": actor["name"],
        }
        body = ISSUE_RESOLVED_MESSAGE_TEMPLATE.format(**context)

    elif action == "assigned":
        context = {
            "title": topic,
            "assignee": assignee,
            "actor": actor["name"],
        }
        body = ISSUE_ASSIGNED_MESSAGE_TEMPLATE.format(**context)

    elif action == "ignored":
        context = {
            "title": topic,
            "actor": actor["name"],
        }
        body = ISSUE_IGNORED_MESSAGE_TEMPLATE.format(**context)

    else:
        raise UnsupportedWebhookEventTypeError("unknown-issue-action type")

    return (topic, body)


def handle_deprecated_payload(payload: Dict[str, Any]) -> Tuple[str, str]:
    topic = "{}".format(payload.get("project_name"))
    body = DEPRECATED_EXCEPTION_MESSAGE_TEMPLATE.format(
        level=payload["level"].upper(),
        url=payload.get("url"),
        message=payload.get("message"),
    )
    return (topic, body)


def transform_webhook_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Attempt to use webhook payload for the notification.

    When the integration is configured as a webhook, instead of being added as
    an internal integration, the payload is slightly different, but has all the
    required information for sending a notification. We transform this payload to
    look like the payload from a "properly configured" integration.
    """
    event = payload.get("event", {})
    # deprecated payloads don't have event_id
    event_id = event.get("event_id")
    if not event_id:
        return None

    event_path = f"events/{event_id}/"
    event["web_url"] = urljoin(payload["url"], event_path)
    timestamp = event.get("timestamp", event["received"])
    event["datetime"] = datetime.fromtimestamp(timestamp, timezone.utc).isoformat(
        timespec="microseconds"
    )
    return payload


@webhook_view("Sentry")
@typed_endpoint
def api_sentry_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[Dict[str, Any]],
) -> HttpResponse:
    data = payload.get("data", None)

    if data is None:
        data = transform_webhook_payload(payload)

    # We currently support two types of payloads: events and issues.
    if data:
        if "event" in data:
            topic, body = handle_event_payload(data["event"])
        elif "issue" in data:
            topic, body = handle_issue_payload(payload["action"], data["issue"], payload["actor"])
        else:
            raise UnsupportedWebhookEventTypeError(str(list(data.keys())))
    else:
        topic, body = handle_deprecated_payload(payload)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
