import importlib
import requests
import functools
from requests.models import Response
from urllib.parse import unquote

from django.http import HttpRequest
from django.utils.translation import ugettext as _
from typing import Any, Dict, Callable, List, Optional, Union

from zerver.lib.actions import check_send_stream_message, \
    check_send_private_message, send_rate_limited_pm_notification_to_bot_owner
from zerver.lib.bot_config import ConfigError, get_bot_config
from zerver.lib.exceptions import StreamDoesNotExistError, JsonableError, \
    ErrorCode, UnexpectedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.send_email import FromAddress
from zerver.models import UserProfile, BotConfigData


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

class MissingHTTPEventHeader(JsonableError):
    code = ErrorCode.MISSING_HTTP_EVENT_HEADER
    data_fields = ['header']

    def __init__(self, header: str) -> None:
        self.header = header

    @staticmethod
    def msg_format() -> str:
        return _("Missing the HTTP event header '{header}'")

class ThirdPartyAPICallbackError(JsonableError):
    code = ErrorCode.THIRD_PARTY_API_RESPONSE_ERROR
    data_fields = ['bot', 'http_status_code', 'endpoint']

    def __init__(self, bot: UserProfile, endpoint: str,
                 http_status_code: int) -> None:
        self.bot = bot.full_name
        self.endpoint = endpoint
        self.http_status_code = http_status_code

    @staticmethod
    def msg_format() -> str:
        return _("API Callback to {endpoint} via. the \"{bot}\" bot failed \
with status {http_status_code}.")

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

def standardize_headers(input_headers: Union[None, Dict[str, Any]]) -> Dict[str, str]:
    """ This method can be used to standardize a dictionary of headers with
    the standard format that Django expects. For reference, refer to:
    https://docs.djangoproject.com/en/2.2/ref/request-response/#django.http.HttpRequest.headers

    NOTE: Historically, Django's headers were not case-insensitive. We're still
    capitalizing our headers to make it easier to compare/search later if required.
    """
    canonical_headers = {}

    if not input_headers:
        return {}

    for raw_header in input_headers:
        polished_header = raw_header.upper().replace("-", "_")
        if polished_header not in["CONTENT_TYPE", "CONTENT_LENGTH"]:
            if not polished_header.startswith("HTTP_"):
                polished_header = "HTTP_" + polished_header
        canonical_headers[polished_header] = str(input_headers[raw_header])

    return canonical_headers

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
    view_module_name = "zerver.webhooks.{integration_name}.view".format(
        integration_name=integration_name
    )
    try:
        # TODO: We may want to migrate to a more explicit registration
        # strategy for this behavior rather than a try/except import.
        view_module = importlib.import_module(view_module_name)
        fixture_to_headers = view_module.fixture_to_headers  # type: ignore # we do extra exception handling in case it does not exist below.
    except (ImportError, AttributeError):
        return {}
    return fixture_to_headers(fixture_name)

def get_http_headers_from_filename(http_header_key: str) -> Callable[[str], Dict[str, str]]:
    """If an integration requires an event type kind of HTTP header which can
    be easily (statically) determined, then name the fixtures in the format
    of "header_value__other_details" or even "header_value" and the use this
    method in the headers.py file for the integration."""
    def fixture_to_headers(filename: str) -> Dict[str, str]:
        if '__' in filename:
            event_type = filename.split("__")[0]
        else:
            event_type = filename
        return {http_header_key: event_type}
    return fixture_to_headers

class ThirdPartyAPIAmbassador:
    def __init__(
        self, bot: UserProfile, root_url: str="",
        authentication_handler: Optional[Callable[["ThirdPartyAPIAmbassador"],
                                         None]]=None,
        request_preprocessor: Optional[Callable[["ThirdPartyAPIAmbassador"],
                                       None]]=None,
        request_postprocessor: Optional[Callable[["ThirdPartyAPIAmbassador"],
                                        None]]=None,
    ) -> None:

        if bot.is_bot is not True:
            msg = "Ambassador must be a bot. {name} is not a bot".format(
                name=bot.full_name
            )
            raise ValueError(msg)
        self.bot = bot

        self.root_url = root_url

        # we pass these directly to the requests library when making HTTP calls.
        # if we ever need to do stuff like send cookies and files, then this is where
        # we need to begin adding support.
        self._persistent_request_kwargs = {
            "data": {},  # Used in POST requests with an application/x-www-form-urlencoded content type
            "json": {},  # Used in POST requests with an application/json content type
            "params": {},  # Used in a GET request
            "headers": {}
        }  # type: Dict[str, Dict[str, Any]]

        self.request_preprocessor = request_preprocessor
        self.request_postprocessor = request_postprocessor

        self.response_log = []  # type: List[Response]

        if authentication_handler:
            authentication_handler(self)

    @property
    def result(self) -> Optional[Response]:
        try:
            return self.response_log[-1]
        except IndexError:  # nocoverage
            return None

    def update_persistent_request_kwargs(self,
                                         data: Dict[str, Any]={},
                                         json: Dict[str, Any]={},
                                         params: Dict[str, Any]={},
                                         headers: Dict[str, Any]={}) -> None:
        self._persistent_request_kwargs["data"].update(data)
        self._persistent_request_kwargs["json"].update(json)
        self._persistent_request_kwargs["params"].update(params)
        self._persistent_request_kwargs["headers"].update(headers)

    def http_api_callback(self, api_endpoint: str, method: str="post",
                          data: Dict[str, Any]={},
                          json: Dict[str, Any]={},
                          params: Dict[str, Any]={},
                          headers: Dict[str, Any]={}) -> Response:
        data.update(self._persistent_request_kwargs["data"])
        json.update(self._persistent_request_kwargs["json"])
        params.update(self._persistent_request_kwargs["params"])
        headers.update(self._persistent_request_kwargs["headers"])

        if self.request_preprocessor:
            self.request_preprocessor(self)

        if api_endpoint.startswith("/"):
            if self.root_url != "":
                # Then allow relative addressing.
                api_endpoint = self.root_url + api_endpoint
            else:
                raise ValueError("%s attempted to call a relative URL address without a root URL.")
        # TODO: Improve error reporting in cases like this. Maybe notify the bot
        #  owner about what just happened.

        response = requests.request(method, api_endpoint, data=data, json=json,
                                    params=params, headers=headers)
        self.response_log.append(response)

        if self.request_postprocessor:
            self.request_postprocessor(self)

        status = response.status_code
        if not status == 200:
            raise ThirdPartyAPICallbackError(self.bot, api_endpoint, status)

        return response

def api_token_auth_handler(ambassador: ThirdPartyAPIAmbassador,
                           mode: str="form",
                           param_key: str="token",
                           config_element_key: str="api_token") -> None:
    # NOTE: Since this method can throw an exception if the bot config element
    # doesn't exist, so if needed wrap the ThirdPartyAPIAmbassador
    # instantiation inside a try/except block.
    try:
        bot_config = get_bot_config(bot_profile=ambassador.bot)
        api_token = bot_config.get(config_element_key, None)
        if api_token is None:
            raise BotConfigData.DoesNotExist
    except BotConfigData.DoesNotExist:
        raise ConfigError("The \"{bot}\" bot is missing a configuration \
element: \"{key}\"".format(bot=ambassador.bot.full_name,
                           key=config_element_key))

    auth = {param_key: api_token}
    if mode == "url":
        ambassador.update_persistent_request_kwargs(params=auth)
    elif mode == "form":
        ambassador.update_persistent_request_kwargs(data=auth)
    elif mode == "json":
        ambassador.update_persistent_request_kwargs(json=auth)
    elif mode == "headers":
        ambassador.update_persistent_request_kwargs(headers=auth)
    else:  # nocoverage
        raise ValueError('{mode} is an invalid mode for \
api_token_auth_handler. The mode must be one one of "url", "form", "json", or\
"headers".'.format(mode=mode))

def generate_api_token_auth_handler(mode: str="form",
                                    param_key: str="token",
                                    config_element_key: str="api_token") -> Callable[..., None]:
    return functools.partial(api_token_auth_handler,
                             mode=mode,
                             param_key=param_key,
                             config_element_key=config_element_key)
