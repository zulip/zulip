import fnmatch
import importlib
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import unquote

from django.http import HttpRequest
from django.utils.translation import gettext as _
from pydantic import Json
from typing_extensions import Annotated, TypeAlias

from zerver.actions.message_send import (
    check_send_private_message,
    check_send_stream_message,
    check_send_stream_message_by_id,
    send_rate_limited_pm_notification_to_bot_owner,
)
from zerver.lib.exceptions import ErrorCode, JsonableError, StreamDoesNotExistError
from zerver.lib.request import RequestNotes
from zerver.lib.send_email import FromAddress
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.models import UserProfile

MISSING_EVENT_HEADER_MESSAGE = """\
Hi there!  Your bot {bot_name} just sent an HTTP request to {request_path} that
is missing the HTTP {header_name} header.  Because this header is how
{integration_name} indicates the event type, this usually indicates a configuration
issue, where you either entered the URL for a different integration, or are running
an older version of the third-party service that doesn't provide that header.
Contact {support_email} if you need help debugging!
"""

INVALID_JSON_MESSAGE = """
Hi there! It looks like you tried to set up the Zulip {webhook_name} integration,
but didn't correctly configure the webhook to send data in the JSON format
that this integration expects!
"""

SETUP_MESSAGE_TEMPLATE = "{integration} webhook has been successfully configured"
SETUP_MESSAGE_USER_PART = " by {user_name}"

OptionalUserSpecifiedTopicStr: TypeAlias = Annotated[Optional[str], ApiParamConfig("topic")]


def get_setup_webhook_message(integration: str, user_name: Optional[str] = None) -> str:
    content = SETUP_MESSAGE_TEMPLATE.format(integration=integration)
    if user_name:
        content += SETUP_MESSAGE_USER_PART.format(user_name=user_name)
    content = f"{content}."
    return content


def notify_bot_owner_about_invalid_json(
    user_profile: UserProfile, webhook_client_name: str
) -> None:
    send_rate_limited_pm_notification_to_bot_owner(
        user_profile,
        user_profile.realm,
        INVALID_JSON_MESSAGE.format(webhook_name=webhook_client_name).strip(),
    )


class MissingHTTPEventHeaderError(JsonableError):
    code = ErrorCode.MISSING_HTTP_EVENT_HEADER
    data_fields = ["header"]

    def __init__(self, header: str) -> None:
        self.header = header

    @staticmethod
    def msg_format() -> str:
        return _("Missing the HTTP event header '{header}'")


@typed_endpoint
def check_send_webhook_message(
    request: HttpRequest,
    user_profile: UserProfile,
    topic: str,
    body: str,
    complete_event_type: Optional[str] = None,
    *,
    stream: Optional[str] = None,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
    only_events: Optional[Json[List[str]]] = None,
    exclude_events: Optional[Json[List[str]]] = None,
    unquote_url_parameters: bool = False,
) -> None:
    if complete_event_type is not None and (
        # Here, we implement Zulip's generic support for filtering
        # events sent by the third-party service.
        #
        # If complete_event_type is passed to this function, we will check the event
        # type against user configured lists of only_events and exclude events.
        # If the event does not satisfy the configuration, the function will return
        # without sending any messages.
        #
        # We match items in only_events and exclude_events using Unix
        # shell-style wildcards.
        (
            only_events is not None
            and all(not fnmatch.fnmatch(complete_event_type, pattern) for pattern in only_events)
        )
        or (
            exclude_events is not None
            and any(fnmatch.fnmatch(complete_event_type, pattern) for pattern in exclude_events)
        )
    ):
        return

    client = RequestNotes.get_notes(request).client
    assert client is not None
    if stream is None:
        assert user_profile.bot_owner is not None
        check_send_private_message(user_profile, client, user_profile.bot_owner, body)
    else:
        # Some third-party websites (such as Atlassian's Jira), tend to
        # double escape their URLs in a manner that escaped space characters
        # (%20) are never properly decoded. We work around that by making sure
        # that the URL parameters are decoded on our end.
        if unquote_url_parameters:
            stream = unquote(stream)

        if user_specified_topic is not None:
            topic = user_specified_topic
            if unquote_url_parameters:
                topic = unquote(topic)

        try:
            if stream.isdecimal():
                check_send_stream_message_by_id(user_profile, client, int(stream), topic, body)
            else:
                check_send_stream_message(user_profile, client, stream, topic, body)
        except StreamDoesNotExistError:
            # A direct message will be sent to the bot_owner by check_message,
            # notifying that the webhook bot just tried to send a message to a
            # non-existent stream, so we don't need to re-raise it since it
            # clutters up webhook-errors.log
            pass


def standardize_headers(input_headers: Union[None, Dict[str, Any]]) -> Dict[str, str]:
    """This method can be used to standardize a dictionary of headers with
    the standard format that Django expects. For reference, refer to:
    https://docs.djangoproject.com/en/3.2/ref/request-response/#django.http.HttpRequest.headers

    NOTE: Historically, Django's headers were not case-insensitive. We're still
    capitalizing our headers to make it easier to compare/search later if required.
    """
    canonical_headers = {}

    if not input_headers:
        return {}

    for raw_header in input_headers:
        polished_header = raw_header.upper().replace("-", "_")
        if polished_header not in [
            "CONTENT_TYPE",
            "CONTENT_LENGTH",
        ] and not polished_header.startswith("HTTP_"):
            polished_header = "HTTP_" + polished_header
        canonical_headers[polished_header] = str(input_headers[raw_header])

    return canonical_headers


def validate_extract_webhook_http_header(
    request: HttpRequest, header: str, integration_name: str, fatal: bool = True
) -> Optional[str]:
    assert request.user.is_authenticated

    extracted_header = request.headers.get(header)
    if extracted_header is None and fatal:
        message_body = MISSING_EVENT_HEADER_MESSAGE.format(
            bot_name=request.user.full_name,
            request_path=request.path,
            header_name=header,
            integration_name=integration_name,
            support_email=FromAddress.SUPPORT,
        )
        send_rate_limited_pm_notification_to_bot_owner(
            request.user, request.user.realm, message_body
        )

        raise MissingHTTPEventHeaderError(header)

    return extracted_header


def get_fixture_http_headers(integration_name: str, fixture_name: str) -> Dict["str", "str"]:
    """For integrations that require custom HTTP headers for some (or all)
    of their test fixtures, this method will call a specially named
    function from the target integration module to determine what set
    of HTTP headers goes with the given test fixture.
    """
    view_module_name = f"zerver.webhooks.{integration_name}.view"
    try:
        # TODO: We may want to migrate to a more explicit registration
        # strategy for this behavior rather than a try/except import.
        view_module = importlib.import_module(view_module_name)
        fixture_to_headers = view_module.fixture_to_headers
    except (ImportError, AttributeError):
        return {}
    return fixture_to_headers(fixture_name)


def get_http_headers_from_filename(http_header_key: str) -> Callable[[str], Dict[str, str]]:
    """If an integration requires an event type kind of HTTP header which can
    be easily (statically) determined, then name the fixtures in the format
    of "header_value__other_details" or even "header_value" and the use this
    method in the headers.py file for the integration."""

    def fixture_to_headers(filename: str) -> Dict[str, str]:
        if "__" in filename:
            event_type = filename.split("__")[0]
        else:
            event_type = filename
        return {http_header_key: event_type}

    return fixture_to_headers


def unix_milliseconds_to_timestamp(milliseconds: Any, webhook: str) -> datetime:
    """If an integration requires time input in unix milliseconds, this helper
    checks to ensure correct type and will catch any errors related to type or
    value and raise a JsonableError.
    Returns a datetime representing the time."""
    try:
        # timestamps are in milliseconds so divide by 1000
        seconds = milliseconds / 1000
        return timestamp_to_datetime(seconds)
    except (ValueError, TypeError):
        raise JsonableError(
            _("The {webhook} webhook expects time in milliseconds.").format(webhook=webhook)
        )
