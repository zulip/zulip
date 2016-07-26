from __future__ import absolute_import

from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_list, check_bool
from zerver.models import PushDeviceToken, UserProfile

def add_push_device_token(request, user_profile, token_str, kind, ios_app_id=None):
    # type: (HttpRequest, UserProfile, str, int, Optional[str]) -> HttpResponse
    if token_str == '' or len(token_str) > 4096:
        return json_error(_('Empty or invalid length token'))

    # If another user was previously logged in on the same device and didn't
    # properly log out, the token will still be registered to the wrong account
    PushDeviceToken.objects.filter(token=token_str).delete()

    # Overwrite with the latest value
    token, created = PushDeviceToken.objects.get_or_create(user=user_profile,
                                                           token=token_str,
                                                           kind=kind,
                                                           ios_app_id=ios_app_id)
    if not created:
        token.last_updated = now()
        token.save(update_fields=['last_updated'])

    return json_success()

@has_request_variables
def add_apns_device_token(request, user_profile, token=REQ(), appid=REQ(default=settings.ZULIP_IOS_APP_ID)):
    # type: (HttpRequest, UserProfile, str, str) -> HttpResponse
    return add_push_device_token(request, user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)

@has_request_variables
def add_android_reg_id(request, user_profile, token_str=REQ("token")):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    return add_push_device_token(request, user_profile, token_str, PushDeviceToken.GCM)

def remove_push_device_token(request, user_profile, token_str, kind):
    # type: (HttpRequest, UserProfile, str, int) -> HttpResponse
    if token_str == '' or len(token_str) > 4096:
        return json_error(_('Empty or invalid length token'))

    try:
        token = PushDeviceToken.objects.get(token=token_str, kind=kind)
        token.delete()
    except PushDeviceToken.DoesNotExist:
        return json_error(_("Token does not exist"))

    return json_success()

@has_request_variables
def remove_apns_device_token(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    return remove_push_device_token(request, user_profile, token, PushDeviceToken.APNS)

@has_request_variables
def remove_android_reg_id(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    return remove_push_device_token(request, user_profile, token, PushDeviceToken.GCM)
