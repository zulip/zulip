from __future__ import absolute_import

from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.lib.push_notifications import add_push_device_token
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_list, check_bool
from zerver.models import PushDeviceToken, UserProfile

@has_request_variables
def add_apns_device_token(request, user_profile, token=REQ(), appid=REQ(default=settings.ZULIP_IOS_APP_ID)):
    # type: (HttpRequest, UserProfile, str, str) -> HttpResponse
    add_push_device_token(user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)
    return json_success()

@has_request_variables
def add_android_reg_id(request, user_profile, token_str=REQ("token")):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    add_push_device_token(user_profile, token_str, PushDeviceToken.GCM)
    return json_success()

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
