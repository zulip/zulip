import hashlib
import json
import random
import secrets
from abc import ABC, abstractmethod
from base64 import b32encode
from typing import Any, Dict, Mapping, Optional
from urllib.parse import quote, urlencode, urljoin

import requests
from defusedxml import ElementTree
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.middleware import csrf
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib import OAuth2Session

from zerver.decorator import REQ, has_request_variables, zulip_login_required
from zerver.lib.actions import do_set_zoom_token
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.pysa import mark_sanitized
from zerver.lib.response import json_error, json_success
from zerver.lib.subdomains import get_subdomain
from zerver.lib.url_encoding import add_query_arg_to_redirect_url, add_query_to_redirect_url
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile, get_realm


class InvalidTokenError(JsonableError):
    code = ErrorCode.INVALID_TOKEN

    def __init__(self) -> None:
        super().__init__(_("Invalid access token"))


class AuthenticatedVideoApplication(ABC):
    @property
    @abstractmethod
    def application_name(self) -> str:
        pass

    @property
    @abstractmethod
    def client_id(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def client_secret(self) -> Optional[str]:
        pass

    @property
    def authorization_scope(self) -> Optional[str]:
        return None

    @property
    @abstractmethod
    def authorization_url(self) -> str:
        pass

    @property
    @abstractmethod
    def token_url(self) -> str:
        pass

    @property
    @abstractmethod
    def auto_refresh_url(self) -> str:
        pass

    @property
    @abstractmethod
    def create_meeting_url(self) -> str:
        pass

    @abstractmethod
    def get_token(self, user: UserProfile) -> Optional[object]:
        pass

    @abstractmethod
    def update_token(self, user: UserProfile, token: Optional[Dict[str, object]]) -> None:
        pass

    @abstractmethod
    def get_meeting_details(self, response: HttpResponse) -> Mapping[str, Any]:
        pass

    def __get_session(self, user: UserProfile) -> OAuth2Session:
        if self.client_id is None or self.client_secret is None:
            raise JsonableError(_("Credentials have not been configured"))

        return OAuth2Session(
            self.client_id,
            scope=self.authorization_scope,
            redirect_uri=urljoin(
                settings.ROOT_DOMAIN_URI, f"/calls/{self.application_name}/complete"
            ),
            auto_refresh_url=self.auto_refresh_url,
            auto_refresh_kwargs={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            token=self.get_token(user),
            token_updater=lambda token: self.update_token(user, token),
        )

    def __get_sid(self, request: HttpRequest) -> str:
        # This is used to prevent CSRF attacks on the OAuth
        # authentication flow.  We want this value to be unpredictable and
        # tied to the session, but we don’t want to expose the main CSRF
        # token directly to the server.

        csrf.get_token(request)
        # Use 'mark_sanitized' to cause Pysa to ignore the flow of user controlled
        # data out of this function. 'request.META' is indeed user controlled, but
        # post-HMAC output is no longer meaningfully controllable.
        return mark_sanitized(
            ""
            if getattr(request, "_dont_enforce_csrf_checks", False)
            else salted_hmac(
                f"Zulip {self.application_name.capitalize()} sid", request.META["CSRF_COOKIE"]
            ).hexdigest()
        )

    def register_user(self, request: HttpRequest, **kwargs: Any) -> HttpResponse:
        oauth = self.__get_session(request.user)
        authorization_url, state = oauth.authorization_url(
            self.authorization_url,
            state=json.dumps(
                {"realm": get_subdomain(request), "sid": self.__get_sid(request)},
            ),
            **kwargs,
        )
        return redirect(authorization_url)

    def complete_user(
        self, request: HttpRequest, sid: str, code: str, **kwargs: Any
    ) -> HttpResponse:
        if not constant_time_compare(sid, self.__get_sid(request)):
            raise JsonableError(_("Invalid session identifier"))

        oauth = self.__get_session(request.user)
        try:
            token = oauth.fetch_token(
                self.token_url, code=code, client_secret=self.client_secret, **kwargs
            )
        except OAuth2Error:
            raise JsonableError(_("Invalid credentials"))

        self.update_token(request.user, token)
        return render(request, "zerver/close_window.html")

    def make_video_call(
        self, request: HttpRequest, user: UserProfile, json: Optional[Any] = {}, **kwargs: Any
    ) -> HttpResponse:
        oauth = self.__get_session(user)
        if not oauth.authorized:
            raise InvalidTokenError

        try:
            res = oauth.post(self.create_meeting_url, json=json, **kwargs)
        except OAuth2Error:
            self.update_token(user, None)
            raise InvalidTokenError

        if res.status_code == 401:
            self.update_token(user, None)
            raise InvalidTokenError
        elif not res.ok:
            raise JsonableError(_("Failed to create call"))

        return json_success(self.get_meeting_details(res))


class ZoomVideo(AuthenticatedVideoApplication):
    application_name = "zoom"

    @property
    def client_id(self) -> Optional[str]:
        return settings.VIDEO_ZOOM_CLIENT_ID

    @property
    def client_secret(self) -> Optional[str]:
        return settings.VIDEO_ZOOM_CLIENT_SECRET

    authorization_url = urljoin(settings.VIDEO_ZOOM_API_URL, "/oauth/authorize")
    token_url = urljoin(settings.VIDEO_ZOOM_API_URL, "/oauth/token")
    auto_refresh_url = urljoin(settings.VIDEO_ZOOM_API_URL, "/oauth/token")
    create_meeting_url = urljoin(settings.VIDEO_ZOOM_API_URL, "/v2/users/me/meetings")

    def get_token(self, user: UserProfile) -> Optional[object]:
        return user.zoom_token

    def update_token(self, user: UserProfile, token: Optional[Dict[str, object]]) -> None:
        do_set_zoom_token(user, token)

    def get_meeting_details(self, response: HttpResponse) -> Mapping[str, Any]:
        return {"url": response.json()["join_url"]}

    def deauthorize_user(self, request: HttpRequest) -> HttpResponse:
        data = json.loads(request.body)
        payload = data["payload"]
        if payload["user_data_retention"] == "false":
            requests.post(
                urljoin(settings.VIDEO_ZOOM_API_URL, "/oauth/data/compliance"),
                json={
                    "client_id": self.client_id,
                    "user_id": payload["user_id"],
                    "account_id": payload["account_id"],
                    "deauthorization_event_received": payload,
                    "compliance_completed": True,
                },
                auth=(self.client_id, self.client_secret),
            ).raise_for_status()
        return json_success()


@zulip_login_required
@never_cache
def register_zoom_user(request: HttpRequest) -> HttpResponse:
    return ZoomVideo().register_user(request)


@never_cache
@has_request_variables
def complete_zoom_user(
    request: HttpRequest,
    state: Dict[str, str] = REQ(
        json_validator=check_dict([("realm", check_string)], value_validator=check_string)
    ),
) -> HttpResponse:
    if get_subdomain(request) != state["realm"]:
        return redirect(urljoin(get_realm(state["realm"]).uri, request.get_full_path()))
    return complete_zoom_user_in_realm(request)


@zulip_login_required
@has_request_variables
def complete_zoom_user_in_realm(
    request: HttpRequest,
    code: str = REQ(),
    state: Dict[str, str] = REQ(
        json_validator=check_dict([("sid", check_string)], value_validator=check_string)
    ),
) -> HttpResponse:
    return ZoomVideo().complete_user(request, state["sid"], code)


def make_zoom_video_call(request: HttpRequest, user: UserProfile) -> HttpResponse:
    return ZoomVideo().make_video_call(request, user)


@csrf_exempt
@require_POST
def deauthorize_zoom_user(request: HttpRequest) -> HttpResponse:
    return ZoomVideo().deauthorize_user(request)


def get_bigbluebutton_url(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # https://docs.bigbluebutton.org/dev/api.html#create for reference on the API calls
    # https://docs.bigbluebutton.org/dev/api.html#usage for reference for checksum
    id = "zulip-" + str(random.randint(100000000000, 999999999999))
    password = b32encode(secrets.token_bytes(7))[:10].decode()
    checksum = hashlib.sha1(
        (
            "create"
            + "meetingID="
            + id
            + "&moderatorPW="
            + password
            + "&attendeePW="
            + password
            + "a"
            + settings.BIG_BLUE_BUTTON_SECRET
        ).encode()
    ).hexdigest()
    url = add_query_to_redirect_url(
        "/calls/bigbluebutton/join",
        urlencode(
            {
                "meeting_id": '"' + id + '"',
                "password": '"' + password + '"',
                "checksum": '"' + checksum + '"',
            }
        ),
    )
    return json_success({"url": url})


# We use zulip_login_required here mainly to get access to the user's
# full name from Zulip to prepopulate the user's name in the
# BigBlueButton meeting.  Since the meeting's details are encoded in
# the link the user is clicking, there is no validation tying this
# meeting to the Zulip organization it was created in.
@zulip_login_required
@never_cache
@has_request_variables
def join_bigbluebutton(
    request: HttpRequest,
    meeting_id: str = REQ(json_validator=check_string),
    password: str = REQ(json_validator=check_string),
    checksum: str = REQ(json_validator=check_string),
) -> HttpResponse:
    if settings.BIG_BLUE_BUTTON_URL is None or settings.BIG_BLUE_BUTTON_SECRET is None:
        return json_error(_("Big Blue Button is not configured."))
    else:
        try:
            response = requests.get(
                add_query_to_redirect_url(
                    settings.BIG_BLUE_BUTTON_URL + "api/create",
                    urlencode(
                        {
                            "meetingID": meeting_id,
                            "moderatorPW": password,
                            "attendeePW": password + "a",
                            "checksum": checksum,
                        }
                    ),
                )
            )
            response.raise_for_status()
        except requests.RequestException:
            return json_error(_("Error connecting to the Big Blue Button server."))

        payload = ElementTree.fromstring(response.text)
        if payload.find("messageKey").text == "checksumError":
            return json_error(_("Error authenticating to the Big Blue Button server."))

        if payload.find("returncode").text != "SUCCESS":
            return json_error(_("Big Blue Button server returned an unexpected error."))

        join_params = urlencode(  # type: ignore[type-var] # https://github.com/python/typeshed/issues/4234
            {
                "meetingID": meeting_id,
                "password": password,
                "fullName": request.user.full_name,
            },
            quote_via=quote,
        )

        checksum = hashlib.sha1(
            ("join" + join_params + settings.BIG_BLUE_BUTTON_SECRET).encode()
        ).hexdigest()
        redirect_url_base = add_query_to_redirect_url(
            settings.BIG_BLUE_BUTTON_URL + "api/join", join_params
        )
        return redirect(add_query_arg_to_redirect_url(redirect_url_base, "checksum=" + checksum))
