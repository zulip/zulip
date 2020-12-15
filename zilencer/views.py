import datetime
import logging
from typing import Any, Dict, List, Optional, Union

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext as err_
from django.views.decorators.csrf import csrf_exempt

from analytics.lib.counts import COUNT_STATS
from zerver.decorator import InvalidZulipServerKeyError, require_post
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    send_android_push_notification,
    send_apple_push_notification,
)
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import (
    check_bool,
    check_capped_string,
    check_dict_only,
    check_float,
    check_int,
    check_list,
    check_none_or,
    check_string,
    check_string_fixed_length,
)
from zerver.models import UserProfile
from zerver.views.push_notifications import validate_token
from zilencer.models import (
    RemoteInstallationCount,
    RemotePushDeviceToken,
    RemoteRealmAuditLog,
    RemoteRealmCount,
    RemoteZulipServer,
)


def validate_entity(entity: Union[UserProfile, RemoteZulipServer]) -> RemoteZulipServer:
    if not isinstance(entity, RemoteZulipServer):
        raise JsonableError(err_("must validate with valid Zulip server API key"))
    return entity

def validate_bouncer_token_request(entity: Union[UserProfile, RemoteZulipServer],
                                   token: str, kind: int) -> RemoteZulipServer:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.GCM]:
        raise JsonableError(err_("Invalid token type"))
    server = validate_entity(entity)
    validate_token(token, kind)
    return server

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
        raise JsonableError(_('{} is not a valid hostname').format(hostname))

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
                                user_id: int=REQ(validator=check_int), token: str=REQ(),
                                token_kind: int=REQ(validator=check_int),
                                ios_app_id: Optional[str]=None) -> HttpResponse:
    server = validate_bouncer_token_request(entity, token, token_kind)

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
                                  token: str=REQ(),
                                  token_kind: int=REQ(validator=check_int),
                                  user_id: int=REQ(validator=check_int),
                                  ios_app_id: Optional[str]=None) -> HttpResponse:
    server = validate_bouncer_token_request(entity, token, token_kind)
    deleted = RemotePushDeviceToken.objects.filter(token=token,
                                                   kind=token_kind,
                                                   user_id=user_id,
                                                   server=server).delete()
    if deleted[0] == 0:
        return json_error(err_("Token does not exist"))

    return json_success()

@has_request_variables
def unregister_all_remote_push_devices(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                       user_id: int=REQ(validator=check_int)) -> HttpResponse:
    server = validate_entity(entity)
    RemotePushDeviceToken.objects.filter(user_id=user_id,
                                         server=server).delete()
    return json_success()

@has_request_variables
def remote_server_notify_push(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                              payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    server = validate_entity(entity)

    user_id = payload['user_id']
    gcm_payload = payload['gcm_payload']
    apns_payload = payload['apns_payload']
    gcm_options = payload.get('gcm_options', {})

    android_devices = list(RemotePushDeviceToken.objects.filter(
        user_id=user_id,
        kind=RemotePushDeviceToken.GCM,
        server=server,
    ))

    apple_devices = list(RemotePushDeviceToken.objects.filter(
        user_id=user_id,
        kind=RemotePushDeviceToken.APNS,
        server=server,
    ))

    send_android_push_notification(android_devices, gcm_payload, gcm_options, remote=True)

    send_apple_push_notification(user_id, apple_devices, apns_payload, remote=True)

    return json_success()

def validate_incoming_table_data(server: RemoteZulipServer, model: Any,
                                 rows: List[Dict[str, Any]], is_count_stat: bool=False) -> None:
    last_id = get_last_id_from_server(server, model)
    for row in rows:
        if is_count_stat and row['property'] not in COUNT_STATS:
            raise JsonableError(_("Invalid property {}").format(row['property']))
        if row['id'] <= last_id:
            raise JsonableError(_("Data is out of order."))
        last_id = row['id']

def batch_create_table_data(server: RemoteZulipServer, model: Any,
                            row_objects: Union[List[RemoteRealmCount],
                                               List[RemoteInstallationCount]]) -> None:
    BATCH_SIZE = 1000
    while len(row_objects) > 0:
        try:
            model.objects.bulk_create(row_objects[:BATCH_SIZE])
        except IntegrityError:
            logging.warning(
                "Invalid data saving %s for server %s/%s",
                model._meta.db_table, server.hostname, server.uuid,
            )
            raise JsonableError(_("Invalid data."))
        row_objects = row_objects[BATCH_SIZE:]

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
                                     ]))),
                                 realmauditlog_rows: Optional[List[Dict[str, Any]]]=REQ(
                                     validator=check_list(check_dict_only([
                                         ('id', check_int),
                                         ('realm', check_int),
                                         ('event_time', check_float),
                                         ('backfilled', check_bool),
                                         ('extra_data', check_none_or(check_string)),
                                         ('event_type', check_int),
                                     ])), default=None)) -> HttpResponse:
    server = validate_entity(entity)

    validate_incoming_table_data(server, RemoteRealmCount, realm_counts, True)
    validate_incoming_table_data(server, RemoteInstallationCount, installation_counts, True)
    if realmauditlog_rows is not None:
        validate_incoming_table_data(server, RemoteRealmAuditLog, realmauditlog_rows)

    row_objects = [RemoteRealmCount(
        property=row['property'],
        realm_id=row['realm'],
        remote_id=row['id'],
        server=server,
        end_time=datetime.datetime.fromtimestamp(row['end_time'], tz=datetime.timezone.utc),
        subgroup=row['subgroup'],
        value=row['value']) for row in realm_counts]
    batch_create_table_data(server, RemoteRealmCount, row_objects)

    row_objects = [RemoteInstallationCount(
        property=row['property'],
        remote_id=row['id'],
        server=server,
        end_time=datetime.datetime.fromtimestamp(row['end_time'], tz=datetime.timezone.utc),
        subgroup=row['subgroup'],
        value=row['value']) for row in installation_counts]
    batch_create_table_data(server, RemoteInstallationCount, row_objects)

    if realmauditlog_rows is not None:
        row_objects = [RemoteRealmAuditLog(
            realm_id=row['realm'],
            remote_id=row['id'],
            server=server,
            event_time=datetime.datetime.fromtimestamp(row['event_time'], tz=datetime.timezone.utc),
            backfilled=row['backfilled'],
            extra_data=row['extra_data'],
            event_type=row['event_type']) for row in realmauditlog_rows]
        batch_create_table_data(server, RemoteRealmAuditLog, row_objects)

    return json_success()

def get_last_id_from_server(server: RemoteZulipServer, model: Any) -> int:
    last_count = model.objects.filter(server=server).order_by("remote_id").last()
    if last_count is not None:
        return last_count.remote_id
    return 0

@has_request_variables
def remote_server_check_analytics(request: HttpRequest,
                                  entity: Union[UserProfile, RemoteZulipServer]) -> HttpResponse:
    server = validate_entity(entity)

    result = {
        'last_realm_count_id': get_last_id_from_server(server, RemoteRealmCount),
        'last_installation_count_id': get_last_id_from_server(
            server, RemoteInstallationCount),
        'last_realmauditlog_id': get_last_id_from_server(
            server, RemoteRealmAuditLog),
    }
    return json_success(result)
