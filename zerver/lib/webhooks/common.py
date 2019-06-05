import importlib
from urllib.parse import unquote

from django.http import HttpRequest
from django.utils.translation import ugettext as _
from typing import Optional, Dict, Union, Any

from zerver.lib.actions import check_send_stream_message, \
    check_send_private_message, send_rate_limited_pm_notification_to_bot_owner
from zerver.lib.exceptions import StreamDoesNotExistError, JsonableError, \
    ErrorCode
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.send_email import FromAddress
from zerver.models import UserProfile


MISSING_EVENT_HEADER_MESSAGE = """
Hi there!  Your bot {bot_name} just sent an HTTP request to {request_path} that
is missing the HTTP {header_name} header.  Because this header is how
{integration_name} indicates the event type, this usually indicates a configuration
issue, where you either entered the URL for a different integration, or are running
an older version of the third-party service that doesn't provide that header.
Contact {support_email} if you need help debugging!
"""

INVALID_JSON_MESSAGE = """
Hi there! It looks like you tried to setup the Zulip {webhook_name} integration,
but didn't correctly configure the webhook to send data in the JSON format
that this integration expects!
"""

# Django prefixes all custom HTTP headers with `HTTP_`
DJANGO_HTTP_PREFIX = "HTTP_"

def notify_bot_owner_about_invalid_json(user_profile: UserProfile,
                                        webhook_client_name: str) -> None:
    send_rate_limited_pm_notification_to_bot_owner(
        user_profile, user_profile.realm,
        INVALID_JSON_MESSAGE.format(webhook_name=webhook_client_name).strip()
    )

class UnexpectedWebhookEventType(JsonableError):
    code = ErrorCode.UNEXPECTED_WEBHOOK_EVENT_TYPE
    data_fields = ['webhook_name', 'event_type']

    def __init__(self, webhook_name: str, event_type: Optional[str]) -> None:
        self.webhook_name = webhook_name
        self.event_type = event_type

    @staticmethod
    def msg_format() -> str:
        return _("The '{event_type}' event isn't currently supported by the {webhook_name} webhook")

class MissingHTTPEventHeader(JsonableError):
    code = ErrorCode.MISSING_HTTP_EVENT_HEADER
    data_fields = ['header']

    def __init__(self, header: str) -> None:
        self.header = header

    @staticmethod
    def msg_format() -> str:
        return _("Missing the HTTP event header '{header}'")

@has_request_variables
def check_send_webhook_message(
        request: HttpRequest, user_profile: UserProfile,
        topic: str, body: str, stream: Optional[str]=REQ(default=None),
        user_specified_topic: Optional[str]=REQ("topic", default=None),
        unquote_url_parameters: Optional[bool]=False
) -> None:

    if stream is None:
        assert user_profile.bot_owner is not None
        check_send_private_message(user_profile, request.client,
                                   user_profile.bot_owner, body)
    else:
        # Some third-party websites (such as Atlassian's JIRA), tend to
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
            check_send_stream_message(user_profile, request.client,
                                      stream, topic, body)
        except StreamDoesNotExistError:
            # A PM will be sent to the bot_owner by check_message, notifying
            # that the webhook bot just tried to send a message to a non-existent
            # stream, so we don't need to re-raise it since it clutters up
            # webhook-errors.log
            pass

def parse_headers_dict(custom_headers: Union[None, Dict[str, Any]]) -> Dict[str, str]:
    headers = {}
    if not custom_headers:
        return {}
    for header in custom_headers:
        # Ensure what we return is in the Django HTTP headers format,
        # with HTTP_ prefixes before most actual HTTP header names.
        if header.startswith("HTTP_") or header.startswith("http_"):
            headers[header.upper().replace("-", "_")] = str(custom_headers[header])
        else:
            new_header = header.upper().replace("-", "_")
            if new_header not in ["CONTENT_TYPE", "CONTENT_LENGTH"]:
                new_header = "HTTP_" + new_header
            headers[new_header] = str(custom_headers[header])
    return headers

def validate_extract_webhook_http_header(request: HttpRequest, header: str,
                                         integration_name: str,
                                         fatal: Optional[bool]=True) -> Optional[str]:
    extracted_header = request.META.get(DJANGO_HTTP_PREFIX + header)
    if extracted_header is None and fatal:
        message_body = MISSING_EVENT_HEADER_MESSAGE.format(
            bot_name=request.user.full_name,
            request_path=request.path,
            header_name=header,
            integration_name=integration_name,
            support_email=FromAddress.SUPPORT,
        )
        send_rate_limited_pm_notification_to_bot_owner(
            request.user, request.user.realm, message_body)

        raise MissingHTTPEventHeader(header)

    return extracted_header


def get_fixture_http_headers(integration_name: str,
                             fixture_name: str) -> Dict["str", "str"]:
    """For integrations that require custom HTTP headers for some (or all)
    of their test fixtures, this method will call a specially named
    function from the target integration module to determine what set
    of HTTP headers goes with the given test fixture.
    """

    headers_module_name = "zerver.webhooks.{integration_name}.headers".format(
        integration_name=integration_name)
    try:
        # Try to import the headers.py file. If it does not exist,
        # then that means that the integration does not have any
        # special http headers registered.
        #
        # TODO: We may want to migrate to a more explicit registration
        # strategy for this behavior rather than a try/except import.
        headers_module = importlib.import_module(headers_module_name)
    except ImportError:
        return {}
    try:
        fixture_to_headers = headers_module.fixture_to_headers  # type: ignore # we do extra exception handling in case it does not exist below.
    except AttributeError as e:
        msg = ". The {module_name} module must contain a fixture_to_headers method.".format(
            module_name=headers_module_name
        )
        raise AttributeError(str(e) + msg)
    return fixture_to_headers(fixture_name)
