from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import human_users_only
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    add_push_device_token,
    b64_to_hex,
    remove_push_device_token,
    send_test_push_notification,
)
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import PushDeviceToken, UserProfile


def validate_token(token_str: str, kind: int) -> None:
    if token_str == "" or len(token_str) > 4096:
        raise JsonableError(_("Empty or invalid length token"))
    if kind == PushDeviceToken.APNS:
        # Validate that we can actually decode the token.
        try:
            b64_to_hex(token_str)
        except Exception:
            raise JsonableError(_("Invalid APNS token"))


@human_users_only
@has_request_variables
def add_apns_device_token(
    request: HttpRequest,
    user_profile: UserProfile,
    token: str = REQ(),
    appid: str = REQ(default=settings.ZULIP_IOS_APP_ID),
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    add_push_device_token(user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)
    return json_success(request)


@human_users_only
@has_request_variables
def add_android_reg_id(
    request: HttpRequest, user_profile: UserProfile, token: str = REQ()
) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    add_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success(request)


@human_users_only
@has_request_variables
def remove_apns_device_token(
    request: HttpRequest, user_profile: UserProfile, token: str = REQ()
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    remove_push_device_token(user_profile, token, PushDeviceToken.APNS)
    return json_success(request)


@human_users_only
@has_request_variables
def remove_android_reg_id(
    request: HttpRequest, user_profile: UserProfile, token: str = REQ()
) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    remove_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success(request)


@human_users_only
@has_request_variables
def send_test_push_notification_api(
    request: HttpRequest, user_profile: UserProfile, token: Optional[str] = REQ(default=None)
) -> HttpResponse:
    # If a token is specified in the request, the test notification is supposed to be sent
    # to that device. If no token is provided, the test notification should be sent to
    # all devices registered for the user.
    if token is not None:
        try:
            devices = [PushDeviceToken.objects.get(token=token, user=user_profile)]
        except PushDeviceToken.DoesNotExist:
            raise JsonableError(_("Token does not exist"))
    else:
        devices = list(PushDeviceToken.objects.filter(user=user_profile))

    send_test_push_notification(user_profile, devices)

    return json_success(request)
