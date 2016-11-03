from __future__ import absolute_import

import requests
import json

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
    PushDeviceToken.objects.filter(token=token_str).exclude(user=user_profile).delete()

    # Overwrite with the latest value
    token, created = PushDeviceToken.objects.get_or_create(user=user_profile,
                                                           token=token_str,
                                                           defaults=dict(
                                                               kind=kind,
                                                               ios_app_id=ios_app_id))
    if not created:
        token.last_updated = now()
        token.save(update_fields=['last_updated'])
  
    # If we're sending things to the push notification bouncer
    # register this user with them here
    if settings.PUSH_NOTIFICATION_BOUNCER_URL != '':
      return send_to_push_bouncer(user_profile, token_str, kind, ios_app_id)

    return json_success()

def send_to_push_bouncer(user_profile, token_str, kind, ios_app_id=None):
  # type: (UserProfile, text_type, int, text_type) -> HTTPResponse
    post_data = {
      'server_uuid': settings.ZULIP_ORG_ID,
      'user_id': user_profile.id,
      'token': token_str,
      'token_kind': kind,
    }

    if kind == PushDeviceToken.APNS:
      post_data['ios_app_id'] = ios_app_id

    api_auth=requests.auth.HTTPBasicAuth(settings.ZULIP_ORG_ID, settings.ZULIP_ORG_KEY)
    # todo: what to do about verify & cert
    # todo: user agent ?
    res = requests.post(settings.PUSH_NOTIFICATION_BOUNCER_URL,
      data=json.dumps(post_data),
      auth=api_auth,
      timeout=30,
      headers={"User-agent":"todo", "X-Zulip-Install-ID" : settings.ZULIP_ORG_ID})

    # todo: much better error handling/ should we retry?
    if res.status_code >= 500:
        return json_error(_("Fatal error received from Zulip.org bouncer"))
    elif res.status_code >= 400:
        return json_error(_("Error received from Zulip.org notification bouncer"))
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

    # todo: remove token from bouncer as well

    return json_success()

@has_request_variables
def remove_apns_device_token(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    return remove_push_device_token(request, user_profile, token, PushDeviceToken.APNS)

@has_request_variables
def remove_android_reg_id(request, user_profile, token=REQ()):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    return remove_push_device_token(request, user_profile, token, PushDeviceToken.GCM)
