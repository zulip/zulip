from typing import Any, Dict, List, Optional, Union, cast
import datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.timezone import utc as timezone_utc
from django.utils.translation import ugettext as _, ugettext as err_
from django.views.decorators.csrf import csrf_exempt

from analytics.lib.counts import COUNT_STATS
from zerver.decorator import require_post, InvalidZulipServerKeyError
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import send_android_push_notification, \
    send_apple_push_notification
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_int, check_string, \
    check_capped_string, check_string_fixed_length, check_float, check_none_or, \
    check_dict_only, check_list
from zerver.models import UserProfile
from zerver.views.push_notifications import validate_token
from zilencer.models import RemotePushDeviceToken, RemoteZulipServer, \
    RemoteRealmCount, RemoteInstallationCount

def validate_entity(entity: Union[UserProfile, RemoteZulipServer]) -> None:
    if not isinstance(entity, RemoteZulipServer):
        raise JsonableError(err_("Must validate with valid Zulip server API key"))

def validate_bouncer_token_request(entity: Union[UserProfile, RemoteZulipServer],
                                   token: bytes, kind: int) -> None:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.GCM]:
        raise JsonableError(err_("Invalid token type"))
    validate_entity(entity)
    validate_token(token, kind)

@csrf_exempt
@require_post
@has_request_variables
def register_remote_server(
        request: HttpRequest,
        zulip_org_id: str=REQ(str_validator=check_string_fixed_length(RemoteZulipServer.UUID_LENGTH)),
        zulip_org_key: str=REQ(str_validator=check_string_fixed_length(RemoteZulipServer.API_KEY_LENGTH)),
        hostname: str=REQ(str_validator=check_capped_string(RemoteZulipServer.HOSTNAME_MAX_LENGTH)),
        contact_email: str=REQ(str_validator=check_string),
        new_org_key: Optional[str]=REQ(str_validator=check_string_fixed_length(
            RemoteZulipServer.API_KEY_LENGTH), default=None),
) -> HttpResponse:
    # REQ validated the the field lengths, but we still need to
    # validate the format of these fields.
    try:
        # TODO: Ideally we'd not abuse the URL validator this way
        url_validator = URLValidator()
        url_validator('http://' + hostname)
    except ValidationError:
        raise JsonableError(_('%s is not a valid hostname') % (hostname,))

    try:
        validate_email(contact_email)
    except ValidationError as e:
        raise JsonableError(e.message)

    remote_server, created = RemoteZulipServer.objects.get_or_create(
        uuid=zulip_org_id,
        defaults={'hostname': hostname, 'contact_email': contact_email,
                  'api_key': zulip_org_key})

    if not created:
        if remote_server.api_key != zulip_org_key:
            raise InvalidZulipServerKeyError(zulip_org_id)
        else:
            remote_server.hostname = hostname
            remote_server.contact_email = contact_email
            if new_org_key is not None:
                remote_server.api_key = new_org_key
            remote_server.save()

    return json_success({'created': created})

@has_request_variables
def register_remote_push_device(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                user_id: int=REQ(), token: bytes=REQ(),
                                token_kind: int=REQ(validator=check_int),
                                ios_app_id: Optional[str]=None) -> HttpResponse:
    validate_bouncer_token_request(entity, token, token_kind)
    server = cast(RemoteZulipServer, entity)

    try:
        with transaction.atomic():
            RemotePushDeviceToken.objects.create(
                user_id=user_id,
                server=server,
                kind=token_kind,
                token=token,
                ios_app_id=ios_app_id,
                # last_updated is to be renamed to date_created.
                last_updated=timezone.now())
    except IntegrityError:
        pass

    return json_success()

@has_request_variables
def unregister_remote_push_device(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                  token: bytes=REQ(),
                                  token_kind: int=REQ(validator=check_int),
                                  user_id: int=REQ(),
                                  ios_app_id: Optional[str]=None) -> HttpResponse:
    validate_bouncer_token_request(entity, token, token_kind)
    server = cast(RemoteZulipServer, entity)
    deleted = RemotePushDeviceToken.objects.filter(token=token,
                                                   kind=token_kind,
                                                   user_id=user_id,
                                                   server=server).delete()
    if deleted[0] == 0:
        return json_error(err_("Token does not exist"))

    return json_success()

@has_request_variables
def remote_server_notify_push(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                              payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    validate_entity(entity)
    server = cast(RemoteZulipServer, entity)

    user_id = payload['user_id']
    gcm_payload = payload['gcm_payload']
    apns_payload = payload['apns_payload']
    gcm_options = payload.get('gcm_options', {})

    android_devices = list(RemotePushDeviceToken.objects.filter(
        user_id=user_id,
        kind=RemotePushDeviceToken.GCM,
        server=server
    ))

    apple_devices = list(RemotePushDeviceToken.objects.filter(
        user_id=user_id,
        kind=RemotePushDeviceToken.APNS,
        server=server
    ))

    if android_devices:
        send_android_push_notification(android_devices, gcm_payload, gcm_options, remote=True)

    if apple_devices:
        send_apple_push_notification(user_id, apple_devices, apns_payload, remote=True)

    return json_success()

def validate_count_stats(server: RemoteZulipServer, model: Any,
                         counts: List[Dict[str, Any]]) -> None:
    last_id = get_last_id_from_server(server, model)
    for item in counts:
        if item['property'] not in COUNT_STATS:
            raise JsonableError(_("Invalid property %s" % item['property']))
        if item['id'] <= last_id:
            raise JsonableError(_("Data is out of order."))
        last_id = item['id']

@has_request_variables
def remote_server_post_analytics(request: HttpRequest,
                                 entity: Union[UserProfile, RemoteZulipServer],
                                 realm_counts: List[Dict[str, Any]]=REQ(
                                     validator=check_list(check_dict_only([
                                         ('property', check_string),
                                         ('realm', check_int),
                                         ('id', check_int),
                                         ('end_time', check_float),
                                         ('subgroup', check_none_or(check_string)),
                                         ('value', check_int),
                                     ]))),
                                 installation_counts: List[Dict[str, Any]]=REQ(
                                     validator=check_list(check_dict_only([
                                         ('property', check_string),
                                         ('id', check_int),
                                         ('end_time', check_float),
                                         ('subgroup', check_none_or(check_string)),
                                         ('value', check_int),
                                     ])))) -> HttpResponse:
    validate_entity(entity)
    server = cast(RemoteZulipServer, entity)

    validate_count_stats(server, RemoteRealmCount, realm_counts)
    validate_count_stats(server, RemoteInstallationCount, installation_counts)

    BATCH_SIZE = 1000
    while len(realm_counts) > 0:
        batch = realm_counts[0:BATCH_SIZE]
        realm_counts = realm_counts[BATCH_SIZE:]

        objects_to_create = []
        for item in batch:
            objects_to_create.append(RemoteRealmCount(
                property=item['property'],
                realm_id=item['realm'],
                remote_id=item['id'],
                server=server,
                end_time=datetime.datetime.fromtimestamp(item['end_time'], tz=timezone_utc),
                subgroup=item['subgroup'],
                value=item['value']))
        RemoteRealmCount.objects.bulk_create(objects_to_create)

    while len(installation_counts) > 0:
        batch = installation_counts[0:BATCH_SIZE]
        installation_counts = installation_counts[BATCH_SIZE:]

        objects_to_create = []
        for item in batch:
            objects_to_create.append(RemoteInstallationCount(
                property=item['property'],
                remote_id=item['id'],
                server=server,
                end_time=datetime.datetime.fromtimestamp(item['end_time'], tz=timezone_utc),
                subgroup=item['subgroup'],
                value=item['value']))
        RemoteInstallationCount.objects.bulk_create(objects_to_create)
    return json_success()

def get_last_id_from_server(server: RemoteZulipServer, model: Any) -> int:
    last_count = model.objects.filter(server=server).order_by("remote_id").last()
    if last_count is not None:
        return last_count.remote_id
    return 0

@has_request_variables
def remote_server_check_analytics(request: HttpRequest,
                                  entity: Union[UserProfile, RemoteZulipServer]) -> HttpResponse:
    validate_entity(entity)
    server = cast(RemoteZulipServer, entity)

    result = {
        'last_realm_count_id': get_last_id_from_server(server, RemoteRealmCount),
        'last_installation_count_id': get_last_id_from_server(
            server, RemoteInstallationCount),
    }
    return json_success(result)
