from __future__ import absolute_import

import requests
import json

from typing import Optional, Text

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.lib.push_notifications import add_push_device_token, \
    remove_push_device_token
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_list, check_bool
from zerver.models import PushDeviceToken, UserProfile

def validate_token(token_str):
    # type: (str) -> None
    if token_str == '' or len(token_str) > 4096:
        raise JsonableError(_('Empty or invalid length token'))

@has_request_variables
def add_apns_device_token(request, user_profile, token=REQ(),
                          appid=REQ(default=settings.ZULIP_IOS_APP_ID)):
    # type: (HttpRequest, UserProfile, str, str) -> HttpResponse
    validate_token(token)
    add_push_device_token(user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)
    return json_success()

@has_request_variables
def add_android_reg_id(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    validate_token(token)
    add_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success()

@has_request_variables
def remove_apns_device_token(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    validate_token(token)
    remove_push_device_token(user_profile, token, PushDeviceToken.APNS)
    return json_success()

@has_request_variables
def remove_android_reg_id(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    validate_token(token)
    remove_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success()
