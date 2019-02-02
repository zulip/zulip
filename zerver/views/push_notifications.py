from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import human_users_only
from zerver.lib.push_notifications import add_push_device_token, \
    b64_to_hex, remove_push_device_token
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success
from zerver.models import PushDeviceToken, UserProfile

def validate_token(token_str: bytes, kind: int) -> None:
    if token_str == '' or len(token_str) > 4096:
        raise JsonableError(_('Empty or invalid length token'))
    if kind == PushDeviceToken.APNS:
        # Validate that we can actually decode the token.
        try:
            b64_to_hex(token_str)
        except Exception:
            raise JsonableError(_('Invalid APNS token'))

@human_users_only
@has_request_variables
def add_apns_device_token(request: HttpRequest, user_profile: UserProfile,
                          token: bytes=REQ(),
                          appid: str=REQ(default=settings.ZULIP_IOS_APP_ID)
                          ) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    add_push_device_token(user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)
    return json_success()

@human_users_only
@has_request_variables
def add_android_reg_id(request: HttpRequest, user_profile: UserProfile,
                       token: bytes=REQ()) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    add_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success()

@human_users_only
@has_request_variables
def remove_apns_device_token(request: HttpRequest, user_profile: UserProfile,
                             token: bytes=REQ()) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    remove_push_device_token(user_profile, token, PushDeviceToken.APNS)
    return json_success()

@human_users_only
@has_request_variables
def remove_android_reg_id(request: HttpRequest, user_profile: UserProfile,
                          token: bytes=REQ()) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    remove_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success()
