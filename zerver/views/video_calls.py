import hashlib
import json
import logging
import random
from base64 import b64encode
from urllib.parse import quote, urlencode, urljoin

import requests
from defusedxml import ElementTree
from django.conf import settings
from django.core.signing import Signer
from django.http import HttpRequest, HttpResponse
from django.middleware import csrf
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from oauthlib.oauth2 import OAuth2Error
from pydantic import Json
from requests_oauthlib import OAuth2Session
from typing_extensions import TypedDict

from zerver.actions.video_calls import do_set_zoom_token
from zerver.decorator import zulip_login_required
from zerver.lib.cache import (
    cache_with_key,
    flush_zoom_server_access_token_cache,
    zoom_server_access_token_cache_key,
)
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.partial import partial
from zerver.lib.pysa import mark_sanitized
from zerver.lib.response import json_success
from zerver.lib.subdomains import get_subdomain
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.lib.url_encoding import append_url_query_string
from zerver.lib.utils import assert_is_not_none
from zerver.models import UserProfile
from zerver.models.realms import get_realm


class VideoCallSession(OutgoingSession):
    def __init__(self) -> None:
        super().__init__(role="video_calls", timeout=5)


class InvalidZoomTokenError(JsonableError):
    code = ErrorCode.INVALID_ZOOM_TOKEN

    def __init__(self) -> None:
        super().__init__(_("Invalid Zoom access token"))


class UnknownZoomUserError(JsonableError):
    code = ErrorCode.UNKNOWN_ZOOM_USER

    def __init__(self) -> None:
        super().__init__(_("Unknown Zoom user email"))


def get_zoom_session(user: UserProfile) -> OAuth2Session:
    if settings.VIDEO_ZOOM_CLIENT_ID is None:
        raise JsonableError(_("Zoom credentials have not been configured"))

    client_id = settings.VIDEO_ZOOM_CLIENT_ID
    client_secret = settings.VIDEO_ZOOM_CLIENT_SECRET

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


class StateDictRealm(TypedDict):
    realm: str
    sid: str


class StateDict(TypedDict):
    sid: str


class ZoomVideoSettings(TypedDict):
    host_video: bool
    participant_video: bool


class ZoomPayload(TypedDict):
    settings: ZoomVideoSettings
    default_password: bool


@never_cache
@typed_endpoint
def complete_zoom_user(
    request: HttpRequest,
    *,
    code: str,
    state: Json[StateDictRealm],
) -> HttpResponse:
    if get_subdomain(request) != state["realm"]:
        return redirect(urljoin(get_realm(state["realm"]).url, request.get_full_path()))
    return complete_zoom_user_in_realm(request, code=code, state=state)


@zulip_login_required
@typed_endpoint
def complete_zoom_user_in_realm(
    request: HttpRequest,
    *,
    code: str,
    state: Json[StateDict],
) -> HttpResponse:
    assert request.user.is_authenticated

    if not constant_time_compare(state["sid"], get_zoom_sid(request)):
        raise JsonableError(_("Invalid Zoom session identifier"))

    client_secret = settings.VIDEO_ZOOM_CLIENT_SECRET

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


def make_user_authenticated_zoom_video_call(
    request: HttpRequest,
    user: UserProfile,
    *,
    payload: ZoomPayload,
) -> HttpResponse:
    oauth = get_zoom_session(user)
    if not oauth.authorized:
        raise InvalidZoomTokenError

    try:
        res = oauth.post("https://api.zoom.us/v2/users/me/meetings", json=payload)
    except OAuth2Error:
        do_set_zoom_token(user, None)
        raise InvalidZoomTokenError

    if res.status_code == 401:
        do_set_zoom_token(user, None)
        raise InvalidZoomTokenError
    elif not res.ok:
        raise JsonableError(_("Failed to create Zoom call"))

    return json_success(request, data={"url": res.json()["join_url"]})


@cache_with_key(zoom_server_access_token_cache_key, timeout=3600 - 240)
def get_zoom_server_to_server_access_token(account_id: str) -> str:
    if settings.VIDEO_ZOOM_CLIENT_ID is None:
        raise JsonableError(_("Zoom credentials have not been configured"))

    client_id = settings.VIDEO_ZOOM_CLIENT_ID.encode("utf-8")
    client_secret = str(settings.VIDEO_ZOOM_CLIENT_SECRET).encode("utf-8")

    url = "https://zoom.us/oauth/token"
    data = {"grant_type": "account_credentials", "account_id": account_id}

    client_information = client_id + b":" + client_secret
    encoded_client = b64encode(client_information).decode("ascii")
    headers = {"Host": "zoom.us", "Authorization": f"Basic {encoded_client}"}

    response = VideoCallSession().post(url, data, headers=headers)
    if not response.ok:
        # {reason: 'Bad request', error: 'invalid_request'} for invalid account ID
        # {'reason': 'Invalid client_id or client_secret', 'error': 'invalid_client'}
        raise JsonableError(_("Invalid Zoom credentials"))
    return response.json()["access_token"]


def get_zoom_server_to_server_call(
    user: UserProfile, access_token: str, payload: ZoomPayload
) -> str:
    email = user.delivery_email
    url = f"https://api.zoom.us/v2/users/{email}/meetings"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = VideoCallSession().post(url, json=payload, headers=headers)
    if not response.ok:
        response_dict = response.json()
        zoom_api_error_code = response_dict["code"]
        if zoom_api_error_code == 1001:
            # {code: 1001, message: "User does not exist: {email}"}
            raise UnknownZoomUserError
        if zoom_api_error_code == 124:
            # For the error responses below, we flush any
            # cached access token for the Zoom account.
            # {code: 124, message: "Invalid access token"}
            # {code: 124, message: "Access token is expired"}
            account_id = str(settings.VIDEO_ZOOM_SERVER_TO_SERVER_ACCOUNT_ID)

            # We are managing expiry ourselves, so this shouldn't
            # happen. Log an error, and flush the access token from
            # the cache, so that future requests should proceed.
            logging.error(
                "Unexpected Zoom error 124: %s",
                response_dict.get("message", str(response_dict)),
            )
            flush_zoom_server_access_token_cache(account_id)
        raise JsonableError(_("Failed to create Zoom call"))
    return response.json()["join_url"]


def make_server_authenticated_zoom_video_call(
    request: HttpRequest,
    user: UserProfile,
    *,
    payload: ZoomPayload,
) -> HttpResponse:
    account_id = str(settings.VIDEO_ZOOM_SERVER_TO_SERVER_ACCOUNT_ID)
    access_token = get_zoom_server_to_server_access_token(account_id)
    url = get_zoom_server_to_server_call(user, access_token, payload)
    return json_success(request, data={"url": url})


@typed_endpoint
def make_zoom_video_call(
    request: HttpRequest,
    user: UserProfile,
    *,
    is_video_call: Json[bool] = True,
) -> HttpResponse:
    # The meeting host has the ability to configure both their own and
    # participants' default video on/off state for the meeting. That's
    # why when creating a meeting, configure the video on/off default
    # according to the desired call type. Each Zoom user can still have
    # their own personal setting to not start video by default.
    video_settings = ZoomVideoSettings(host_video=is_video_call, participant_video=is_video_call)
    payload = ZoomPayload(
        settings=video_settings,
        # Generate a default password depending on the user settings. This will
        # result in the password being appended to the returned Join URL.
        #
        # If we don't request a password to be set, the waiting room will be
        # forcibly enabled in Zoom organizations that require some kind of
        # authentication for all meetings.
        default_password=True,
    )
    if settings.VIDEO_ZOOM_SERVER_TO_SERVER_ACCOUNT_ID is not None:
        return make_server_authenticated_zoom_video_call(request, user, payload=payload)
    return make_user_authenticated_zoom_video_call(request, user, payload=payload)


@csrf_exempt
@require_POST
@typed_endpoint_without_parameters
def deauthorize_zoom_user(request: HttpRequest) -> HttpResponse:
    return json_success(request)


@typed_endpoint
def get_bigbluebutton_url(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    meeting_name: str,
    voice_only: Json[bool] = False,
) -> HttpResponse:
    # https://docs.bigbluebutton.org/dev/api.html#create for reference on the API calls
    # https://docs.bigbluebutton.org/dev/api.html#usage for reference for checksum
    id = "zulip-" + str(random.randint(100000000000, 999999999999))

    # We sign our data here to ensure a Zulip user cannot tamper with
    # the join link to gain access to other meetings that are on the
    # same bigbluebutton server.
    signed = Signer().sign_object(
        {
            "meeting_id": id,
            "name": meeting_name,
            "lock_settings_disable_cam": voice_only,
            "moderator": request.user.id,
        }
    )
    url = append_url_query_string("/calls/bigbluebutton/join", "bigbluebutton=" + signed)
    return json_success(request, {"url": url})


# We use zulip_login_required here mainly to get access to the user's
# full name from Zulip to prepopulate the user's name in the
# BigBlueButton meeting.  Since the meeting's details are encoded in
# the link the user is clicking, there is no validation tying this
# meeting to the Zulip organization it was created in.
@zulip_login_required
@never_cache
@typed_endpoint
def join_bigbluebutton(request: HttpRequest, *, bigbluebutton: str) -> HttpResponse:
    assert request.user.is_authenticated

    if settings.BIG_BLUE_BUTTON_URL is None or settings.BIG_BLUE_BUTTON_SECRET is None:
        raise JsonableError(_("BigBlueButton is not configured."))

    try:
        bigbluebutton_data = Signer().unsign_object(bigbluebutton)
    except Exception:
        raise JsonableError(_("Invalid signature."))

    create_params = urlencode(
        {
            "meetingID": bigbluebutton_data["meeting_id"],
            "name": bigbluebutton_data["name"],
            "lockSettingsDisableCam": bigbluebutton_data["lock_settings_disable_cam"],
        },
        quote_via=quote,
    )

    checksum = hashlib.sha256(
        ("create" + create_params + settings.BIG_BLUE_BUTTON_SECRET).encode()
    ).hexdigest()

    try:
        response = VideoCallSession().get(
            append_url_query_string(settings.BIG_BLUE_BUTTON_URL + "api/create", create_params)
            + "&checksum="
            + checksum
        )
        response.raise_for_status()
    except requests.RequestException:
        raise JsonableError(_("Error connecting to the BigBlueButton server."))

    payload = ElementTree.fromstring(response.text)
    if assert_is_not_none(payload.find("messageKey")).text == "checksumError":
        raise JsonableError(_("Error authenticating to the BigBlueButton server."))

    if assert_is_not_none(payload.find("returncode")).text != "SUCCESS":
        raise JsonableError(_("BigBlueButton server returned an unexpected error."))

    join_params = urlencode(
        {
            "meetingID": bigbluebutton_data["meeting_id"],
            # We use the moderator role only for the user who created the
            # meeting, the attendee role for everyone else, so that only
            # the user who created the meeting can convert a voice-only
            # call to a video call.
            "role": "MODERATOR" if bigbluebutton_data["moderator"] == request.user.id else "VIEWER",
            "fullName": request.user.full_name,
            # https://docs.bigbluebutton.org/dev/api.html#create
            # The createTime option is used to have the user redirected to a link
            # that is only valid for this meeting.
            #
            # Even if the same link in Zulip is used again, a new
            # createTime parameter will be created, as the meeting on
            # the BigBlueButton server has to be recreated. (after a
            # few minutes)
            "createTime": assert_is_not_none(payload.find("createTime")).text,
        },
        quote_via=quote,
    )

    checksum = hashlib.sha256(
        ("join" + join_params + settings.BIG_BLUE_BUTTON_SECRET).encode()
    ).hexdigest()
    redirect_url_base = append_url_query_string(
        settings.BIG_BLUE_BUTTON_URL + "api/join", join_params
    )
    return redirect(append_url_query_string(redirect_url_base, "checksum=" + checksum))
