from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import human_users_only
from zerver.lib.encryption import bytes_to_b64
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    add_push_device_token,
    b64_to_hex,
    remove_push_device_token,
)
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_bool
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


def device_registration_response(request: HttpRequest, token: PushDeviceToken) -> HttpResponse:
    key = token.notification_encryption_key
    assert key is not None
    data = {"encryption_key": bytes_to_b64(key)}
    return json_success(request, data=data)


@human_users_only
@has_request_variables
def add_apns_device_token(
    request: HttpRequest,
    user_profile: UserProfile,
    token: str = REQ(),
    appid: str = REQ(default=settings.ZULIP_IOS_APP_ID),
    notification_encryption_enabled: bool = REQ(default=False, json_validator=check_bool),
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    if notification_encryption_enabled and not settings.PUSH_NOTIFICATION_ENCRYPTION:
        raise JsonableError(_("Notification encryption is disabled"))
    device_token = add_push_device_token(
        user_profile,
        token,
        PushDeviceToken.APNS,
        ios_app_id=appid,
        notification_encryption_enabled=notification_encryption_enabled,
    )

    if notification_encryption_enabled:
        return device_registration_response(request, device_token)

    return json_success(request)


@human_users_only
@has_request_variables
def add_android_reg_id(
    request: HttpRequest,
    user_profile: UserProfile,
    token: str = REQ(),
    notification_encryption_enabled: bool = REQ(default=False, json_validator=check_bool),
) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    if notification_encryption_enabled and not settings.PUSH_NOTIFICATION_ENCRYPTION:
        raise JsonableError(_("Notification encryption is disabled"))
    device_token = add_push_device_token(
        user_profile,
        token,
        PushDeviceToken.GCM,
        notification_encryption_enabled=notification_encryption_enabled,
    )

    if notification_encryption_enabled:
        return device_registration_response(request, device_token)

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
