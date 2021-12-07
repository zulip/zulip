import hashlib
import json
import random
import secrets
from base64 import b32encode
from functools import partial
from typing import Dict
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

from zerver.decorator import zulip_login_required
from zerver.lib.actions import do_set_zoom_token
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.pysa import mark_sanitized
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.subdomains import get_subdomain
from zerver.lib.url_encoding import append_url_query_string
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile, get_realm


class VideoCallSession(OutgoingSession):
    def __init__(self) -> None:
        super().__init__(role="video_calls", timeout=5)


class InvalidZoomTokenError(JsonableError):
    code = ErrorCode.INVALID_ZOOM_TOKEN

    def __init__(self) -> None:
        super().__init__(_("Invalid Zoom access token"))


def get_zoom_session(user: UserProfile) -> OAuth2Session:
    if settings.VIDEO_ZOOM_CLIENT_ID is None:
        raise JsonableError(_("Zoom credentials have not been configured"))

    client_id = settings.VIDEO_ZOOM_CLIENT_ID
    client_secret = settings.VIDEO_ZOOM_CLIENT_SECRET
    if user.realm.string_id in settings.VIDEO_ZOOM_TESTING_REALMS:  # nocoverage
        client_id = settings.VIDEO_ZOOM_TESTING_CLIENT_ID
        client_secret = settings.VIDEO_ZOOM_TESTING_CLIENT_SECRET

    return OAuth2Session(
        client_id,
        redirect_uri=urljoin(settings.ROOT_DOMAIN_URI, "/calls/zoom/complete"),
        auto_refresh_url="https://zoom.us/oauth/token",
        auto_refresh_kwargs={
            "client_id": client_id,
            "client_secret": client_secret,
        },
        token=user.zoom_token,
        token_updater=partial(do_set_zoom_token, user),
    )


def get_zoom_sid(request: HttpRequest) -> str:
    # This is used to prevent CSRF attacks on the Zoom OAuth
    # authentication flow.  We want this value to be unpredictable and
    # tied to the session, but we don’t want to expose the main CSRF
    # token directly to the Zoom server.

    csrf.get_token(request)
    # Use 'mark_sanitized' to cause Pysa to ignore the flow of user controlled
    # data out of this function. 'request.META' is indeed user controlled, but
    # post-HMAC output is no longer meaningfully controllable.
    return mark_sanitized(
        ""
        if getattr(request, "_dont_enforce_csrf_checks", False)
        else salted_hmac("Zulip Zoom sid", request.META["CSRF_COOKIE"]).hexdigest()
    )


@zulip_login_required
@never_cache
def register_zoom_user(request: HttpRequest) -> HttpResponse:
    assert request.user.is_authenticated

    oauth = get_zoom_session(request.user)
    authorization_url, state = oauth.authorization_url(
        "https://zoom.us/oauth/authorize",
        state=json.dumps(
            {"realm": get_subdomain(request), "sid": get_zoom_sid(request)},
        ),
    )
    return redirect(authorization_url)


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
    assert request.user.is_authenticated

    if not constant_time_compare(state["sid"], get_zoom_sid(request)):
        raise JsonableError(_("Invalid Zoom session identifier"))

    client_secret = settings.VIDEO_ZOOM_CLIENT_SECRET
    if request.user.realm.string_id in settings.VIDEO_ZOOM_TESTING_REALMS:  # nocoverage
        client_secret = settings.VIDEO_ZOOM_TESTING_CLIENT_SECRET

    oauth = get_zoom_session(request.user)
    try:
        token = oauth.fetch_token(
            "https://zoom.us/oauth/token",
            code=code,
            client_secret=client_secret,
        )
    except OAuth2Error:
        raise JsonableError(_("Invalid Zoom credentials"))

    do_set_zoom_token(request.user, token)
    return render(request, "zerver/close_window.html")


def make_zoom_video_call(request: HttpRequest, user: UserProfile) -> HttpResponse:
    oauth = get_zoom_session(user)
    if not oauth.authorized:
        raise InvalidZoomTokenError

    try:
        res = oauth.post("https://api.zoom.us/v2/users/me/meetings", json={})
    except OAuth2Error:
        do_set_zoom_token(user, None)
        raise InvalidZoomTokenError

    if res.status_code == 401:
        do_set_zoom_token(user, None)
        raise InvalidZoomTokenError
    elif not res.ok:
        raise JsonableError(_("Failed to create Zoom call"))

    return json_success({"url": res.json()["join_url"]})


@csrf_exempt
@require_POST
@has_request_variables
def deauthorize_zoom_user(request: HttpRequest) -> HttpResponse:
    return json_success()


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
    url = append_url_query_string(
        "/calls/bigbluebutton/join",
        urlencode(
            {
                "meeting_id": id,
                "password": password,
                "checksum": checksum,
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
    meeting_id: str = REQ(),
    password: str = REQ(),
    checksum: str = REQ(),
) -> HttpResponse:
    assert request.user.is_authenticated

    if settings.BIG_BLUE_BUTTON_URL is None or settings.BIG_BLUE_BUTTON_SECRET is None:
        raise JsonableError(_("BigBlueButton is not configured."))
    else:
        try:
            response = VideoCallSession().get(
                append_url_query_string(
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
            raise JsonableError(_("Error connecting to the BigBlueButton server."))

        payload = ElementTree.fromstring(response.text)
        if payload.find("messageKey").text == "checksumError":
            raise JsonableError(_("Error authenticating to the BigBlueButton server."))

        if payload.find("returncode").text != "SUCCESS":
            raise JsonableError(_("BigBlueButton server returned an unexpected error."))

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
        redirect_url_base = append_url_query_string(
            settings.BIG_BLUE_BUTTON_URL + "api/join", join_params
        )
        return redirect(append_url_query_string(redirect_url_base, "checksum=" + checksum))
