from functools import partial
import json
from typing import Dict
from urllib.parse import urljoin

from django.conf import settings
from django.http import HttpResponse, HttpRequest
from django.middleware import csrf
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from oauthlib.oauth2 import OAuth2Error
import requests
from requests_oauthlib import OAuth2Session

from zerver.decorator import REQ, has_request_variables, zulip_login_required
from zerver.lib.actions import do_set_zoom_token
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.response import json_success
from zerver.lib.subdomains import get_subdomain
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile, get_realm


class InvalidZoomTokenError(JsonableError):
    code = ErrorCode.INVALID_ZOOM_TOKEN

    def __init__(self) -> None:
        super().__init__(_("Invalid Zoom access token"))


def get_zoom_session(user: UserProfile) -> OAuth2Session:
    if settings.VIDEO_ZOOM_CLIENT_ID is None:
        raise JsonableError(_("Zoom credentials have not been configured"))

    return OAuth2Session(
        settings.VIDEO_ZOOM_CLIENT_ID,
        redirect_uri=urljoin(settings.ROOT_DOMAIN_URI, "/calls/zoom/complete"),
        scope=["meeting:write:admin"],
        auto_refresh_url="https://zoom.us/oauth/token",
        auto_refresh_kwargs={
            "client_id": settings.VIDEO_ZOOM_CLIENT_ID,
            "client_secret": settings.VIDEO_ZOOM_CLIENT_SECRET,
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
    return (
        ""
        if getattr(request, "_dont_enforce_csrf_checks", False)
        else salted_hmac("Zulip Zoom sid", request.META["CSRF_COOKIE"]).hexdigest()
    )


@zulip_login_required
@never_cache
def register_zoom_user(request: HttpRequest) -> HttpResponse:
    oauth = get_zoom_session(request.user)
    authorization_url, state = oauth.authorization_url(
        "https://zoom.us/oauth/authorize",
        state=json.dumps(
            {"realm": get_subdomain(request), "sid": get_zoom_sid(request)}
        ),
    )
    return redirect(authorization_url)


@never_cache
@has_request_variables
def complete_zoom_user(
    request: HttpRequest,
    state: Dict[str, str] = REQ(validator=check_dict([("realm", check_string)])),
) -> HttpResponse:
    if get_subdomain(request) != state["realm"]:
        return redirect(urljoin(get_realm(state["realm"]).uri, request.get_full_path()))
    return complete_zoom_user_in_realm(request)


@zulip_login_required
@has_request_variables
def complete_zoom_user_in_realm(
    request: HttpRequest,
    code: str = REQ(),
    state: Dict[str, str] = REQ(validator=check_dict([("sid", check_string)])),
) -> HttpResponse:
    if not constant_time_compare(state["sid"], get_zoom_sid(request)):
        raise JsonableError(_("Invalid Zoom session identifier"))

    oauth = get_zoom_session(request.user)
    try:
        token = oauth.fetch_token(
            "https://zoom.us/oauth/token",
            code=code,
            client_secret=settings.VIDEO_ZOOM_CLIENT_SECRET,
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
    data = json.loads(request.body.decode("utf-8"))
    payload = data["payload"]
    if payload["user_data_retention"] == "false":
        requests.post(
            "https://api.zoom.us/oauth/data/compliance",
            json={
                "client_id": settings.VIDEO_ZOOM_CLIENT_ID,
                "user_id": payload["user_id"],
                "account_id": payload["account_id"],
                "deauthorization_event_received": payload,
                "compliance_completed": True,
            },
            auth=(settings.VIDEO_ZOOM_CLIENT_ID, settings.VIDEO_ZOOM_CLIENT_SECRET),
        ).raise_for_status()
    return json_success()
