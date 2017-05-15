from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.utils import timezone
from django.http import HttpResponse, HttpRequest

from zilencer.models import Deployment, RemotePushDeviceToken, RemoteZulipServer

from zerver.decorator import has_request_variables, REQ
from zerver.lib.error_notify import do_report_error
from zerver.lib.push_notifications import send_android_push_notification, \
    send_apple_push_notification
from zerver.lib.request import JsonableError
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_dict
from zerver.models import UserProfile, PushDeviceToken, Realm

from typing import Any, Dict, Optional, Union, Text, cast

def validate_entity(entity):
    # type: (Union[UserProfile, RemoteZulipServer]) -> None
    if not isinstance(entity, RemoteZulipServer):
        raise JsonableError(_("Must validate with valid Zulip server API key"))

def validate_bouncer_token_request(entity, token):
    # type: (Union[UserProfile, RemoteZulipServer], Text) -> None
    validate_entity(entity)
    if token == '' or len(token) > 4096:
        raise JsonableError(_("Empty or invalid length token"))

@has_request_variables
def report_error(request, deployment, type=REQ(), report=REQ(validator=check_dict([]))):
    # type: (HttpRequest, Deployment, Text, Dict[str, Any]) -> HttpResponse
    return do_report_error(deployment.name, type, report)

@has_request_variables
def remote_server_register_push(request, entity, user_id=REQ(),
                                token=REQ(), token_kind=REQ(), ios_app_id=None):
    # type: (HttpRequest, Union[UserProfile, RemoteZulipServer], int, Text, int, Optional[Text]) -> HttpResponse
    validate_bouncer_token_request(entity, token)
    server = cast(RemoteZulipServer, entity)

    # If a user logged out on a device and failed to unregister,
    # we should delete any other user associations for this token
    # & RemoteServer pair
    RemotePushDeviceToken.objects.filter(
        token=token, kind=token_kind, server=server).exclude(user_id=user_id).delete()

    # Save or update
    remote_token, created = RemotePushDeviceToken.objects.update_or_create(
        user_id=user_id,
        server=server,
        kind=token_kind,
        token=token,
        defaults=dict(
            ios_app_id=ios_app_id,
            last_updated=timezone.now()))

    return json_success()

@has_request_variables
def remote_server_unregister_push(request, entity, token=REQ(),
                                  token_kind=REQ(), ios_app_id=None):
    # type: (HttpRequest, Union[UserProfile, RemoteZulipServer], Text, int, Optional[Text]) -> HttpResponse
    validate_bouncer_token_request(entity, token)
    server = cast(RemoteZulipServer, entity)
    deleted = RemotePushDeviceToken.objects.filter(token=token,
                                                   kind=token_kind,
                                                   server=server).delete()
    if deleted[0] == 0:
        return json_error(_("Token does not exist"))

    return json_success()

@has_request_variables
def remote_server_push_message(request, entity, user_id=REQ(), data=REQ()):
    # type: (HttpRequest, Union[UserProfile, RemoteZulipServer], int, Text) -> HttpResponse
    if not isinstance(entity, RemoteZulipServer):
        return json_error(_("Must validate with valid Zulip server API key"))
    server = cast(RemoteZulipServer, entity)

    tokens = list(RemotePushDeviceToken.objects.filter(server=server, user_id=user_id))
    if len(tokens) == 0:
        return json_error(_("No valid push devices for this user ID"))
    apple_tokens = [token for token in tokens if token.kind == PushDeviceToken.APNS]
    android_tokens = [token for token in tokens if token.kind == PushDeviceToken.GCM]
    if len(android_tokens) != 0:
        send_android_push_notification(android_tokens, data)
    if len(apple_tokens) != 0:
        send_apple_push_notification(apple_tokens, data)

    return json_success()
