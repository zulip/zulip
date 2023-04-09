import datetime
import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _
from django.utils.translation import gettext as err_
from django.views.decorators.csrf import csrf_exempt

from analytics.lib.counts import COUNT_STATS
from corporate.lib.stripe import do_deactivate_remote_server
from zerver.decorator import require_post
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    UserPushIdentityCompat,
    send_android_push_notification,
    send_apple_push_notification,
)
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
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
from zerver.views.push_notifications import validate_token
from zilencer.auth import InvalidZulipServerKeyError
from zilencer.models import (
    RemoteInstallationCount,
    RemotePushDeviceToken,
    RemoteRealmAuditLog,
    RemoteRealmCount,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
)

logger = logging.getLogger(__name__)


def validate_uuid(uuid: str) -> None:
    try:
        uuid_object = UUID(uuid, version=4)
        # The UUID initialization under some circumstances will modify the uuid
        # string to create a valid UUIDv4, instead of raising a ValueError.
        # The submitted uuid needing to be modified means it's invalid, so
        # we need to check for that condition.
        if str(uuid_object) != uuid:
            raise ValidationError(err_("Invalid UUID"))
    except ValueError:
        raise ValidationError(err_("Invalid UUID"))


def validate_bouncer_token_request(token: str, kind: int) -> None:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.GCM]:
        raise JsonableError(err_("Invalid token type"))
    validate_token(token, kind)


@csrf_exempt
@require_post
@has_request_variables
def deactivate_remote_server(
    request: HttpRequest,
    remote_server: RemoteZulipServer,
) -> HttpResponse:
    do_deactivate_remote_server(remote_server)
    return json_success(request)


@csrf_exempt
@require_post
@has_request_variables
def register_remote_server(
    request: HttpRequest,
    zulip_org_id: str = REQ(str_validator=check_string_fixed_length(RemoteZulipServer.UUID_LENGTH)),
    zulip_org_key: str = REQ(
        str_validator=check_string_fixed_length(RemoteZulipServer.API_KEY_LENGTH)
    ),
    hostname: str = REQ(str_validator=check_capped_string(RemoteZulipServer.HOSTNAME_MAX_LENGTH)),
    contact_email: str = REQ(),
    new_org_key: Optional[str] = REQ(
        str_validator=check_string_fixed_length(RemoteZulipServer.API_KEY_LENGTH), default=None
    ),
) -> HttpResponse:
    # REQ validated the the field lengths, but we still need to
    # validate the format of these fields.
    try:
        # TODO: Ideally we'd not abuse the URL validator this way
        url_validator = URLValidator()
        url_validator("http://" + hostname)
    except ValidationError:
        raise JsonableError(_("{} is not a valid hostname").format(hostname))

    try:
        validate_email(contact_email)
    except ValidationError as e:
        raise JsonableError(e.message)

    try:
        validate_uuid(zulip_org_id)
    except ValidationError as e:
        raise JsonableError(e.message)

    with transaction.atomic():
        remote_server, created = RemoteZulipServer.objects.get_or_create(
            uuid=zulip_org_id,
            defaults={
                "hostname": hostname,
                "contact_email": contact_email,
                "api_key": zulip_org_key,
            },
        )
        if created:
            RemoteZulipServerAuditLog.objects.create(
                event_type=RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED,
                server=remote_server,
                event_time=remote_server.last_updated,
            )
        else:
            if not constant_time_compare(remote_server.api_key, zulip_org_key):
                raise InvalidZulipServerKeyError(zulip_org_id)
            else:
                remote_server.hostname = hostname
                remote_server.contact_email = contact_email
                if new_org_key is not None:
                    remote_server.api_key = new_org_key
                remote_server.save()

    return json_success(request, data={"created": created})


@has_request_variables
def register_remote_push_device(
    request: HttpRequest,
    server: RemoteZulipServer,
    user_id: Optional[int] = REQ(json_validator=check_int, default=None),
    user_uuid: Optional[str] = REQ(default=None),
    token: str = REQ(),
    token_kind: int = REQ(json_validator=check_int),
    ios_app_id: Optional[str] = None,
) -> HttpResponse:
    validate_bouncer_token_request(token, token_kind)

    if user_id is None and user_uuid is None:
        raise JsonableError(_("Missing user_id or user_uuid"))
    if user_id is not None and user_uuid is not None:
        kwargs: Dict[str, object] = {"user_uuid": user_uuid, "user_id": None}
        # Delete pre-existing user_id registration for this user+device to avoid
        # duplication. Further down, uuid registration will be created.
        RemotePushDeviceToken.objects.filter(
            server=server, token=token, kind=token_kind, user_id=user_id
        ).delete()
    else:
        # One of these is None, so these kwargs will lead to a proper registration
        # of either user_id or user_uuid type
        kwargs = {"user_id": user_id, "user_uuid": user_uuid}
    try:
        with transaction.atomic():
            RemotePushDeviceToken.objects.create(
                server=server,
                kind=token_kind,
                token=token,
                ios_app_id=ios_app_id,
                # last_updated is to be renamed to date_created.
                last_updated=timezone.now(),
                **kwargs,
            )
    except IntegrityError:
        pass

    return json_success(request)


@has_request_variables
def unregister_remote_push_device(
    request: HttpRequest,
    server: RemoteZulipServer,
    token: str = REQ(),
    token_kind: int = REQ(json_validator=check_int),
    user_id: Optional[int] = REQ(json_validator=check_int, default=None),
    user_uuid: Optional[str] = REQ(default=None),
    ios_app_id: Optional[str] = None,
) -> HttpResponse:
    validate_bouncer_token_request(token, token_kind)
    user_identity = UserPushIdentityCompat(user_id=user_id, user_uuid=user_uuid)

    deleted = RemotePushDeviceToken.objects.filter(
        user_identity.filter_q(), token=token, kind=token_kind, server=server
    ).delete()
    if deleted[0] == 0:
        raise JsonableError(err_("Token does not exist"))

    return json_success(request)


@has_request_variables
def unregister_all_remote_push_devices(
    request: HttpRequest,
    server: RemoteZulipServer,
    user_id: Optional[int] = REQ(json_validator=check_int, default=None),
    user_uuid: Optional[str] = REQ(default=None),
) -> HttpResponse:
    user_identity = UserPushIdentityCompat(user_id=user_id, user_uuid=user_uuid)

    RemotePushDeviceToken.objects.filter(user_identity.filter_q(), server=server).delete()
    return json_success(request)


def delete_duplicate_registrations(
    registrations: List[RemotePushDeviceToken], server_id: int, user_id: int, user_uuid: str
) -> List[RemotePushDeviceToken]:
    """
    When migrating to support registration by UUID, we introduced a bug where duplicate
    registrations for the same device+user could be created - one by user_id and one by
    user_uuid. Given no good way of detecting these duplicates at database level, we need to
    take advantage of the fact that when a remote server sends a push notification request
    to us, it sends both user_id and user_uuid of the user.
    See https://github.com/zulip/zulip/issues/24969 for reference.

    This function, knowing the user_id and user_uuid of the user, can detect duplicates
    and delete the legacy user_id registration if appropriate.

    Return the list of registrations with the user_id-based duplicates removed.
    """

    # All registrations passed here should be of the same kind (apple vs android).
    assert len({registration.kind for registration in registrations}) == 1
    kind = registrations[0].kind

    tokens_counter = Counter(device.token for device in registrations)

    tokens_to_deduplicate = []
    for key in tokens_counter:
        if tokens_counter[key] <= 1:
            continue
        if tokens_counter[key] > 2:
            raise AssertionError(
                f"More than two registrations for token {key} for user id:{user_id} uuid:{user_uuid}, shouldn't be possible"
            )
        assert tokens_counter[key] == 2
        tokens_to_deduplicate.append(key)

    if not tokens_to_deduplicate:
        return registrations

    logger.info(
        "Deduplicating push registrations for server id:%s user id:%s uuid:%s and tokens:%s",
        server_id,
        user_id,
        user_uuid,
        sorted(tokens_to_deduplicate),
    )
    RemotePushDeviceToken.objects.filter(
        token__in=tokens_to_deduplicate, kind=kind, server_id=server_id, user_id=user_id
    ).delete()

    deduplicated_registrations_to_return = []
    for registration in registrations:
        if registration.token in tokens_to_deduplicate and registration.user_id is not None:
            # user_id registrations are the ones we deleted
            continue
        deduplicated_registrations_to_return.append(registration)

    return deduplicated_registrations_to_return


@has_request_variables
def remote_server_notify_push(
    request: HttpRequest,
    server: RemoteZulipServer,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    user_id = payload.get("user_id")
    user_uuid = payload.get("user_uuid")
    user_identity = UserPushIdentityCompat(user_id, user_uuid)

    gcm_payload = payload["gcm_payload"]
    apns_payload = payload["apns_payload"]
    gcm_options = payload.get("gcm_options", {})

    android_devices = list(
        RemotePushDeviceToken.objects.filter(
            user_identity.filter_q(),
            kind=RemotePushDeviceToken.GCM,
            server=server,
        )
    )
    if android_devices and user_id is not None and user_uuid is not None:
        android_devices = delete_duplicate_registrations(
            android_devices, server.id, user_id, user_uuid
        )

    apple_devices = list(
        RemotePushDeviceToken.objects.filter(
            user_identity.filter_q(),
            kind=RemotePushDeviceToken.APNS,
            server=server,
        )
    )
    if apple_devices and user_id is not None and user_uuid is not None:
        apple_devices = delete_duplicate_registrations(apple_devices, server.id, user_id, user_uuid)

    logger.info(
        "Sending mobile push notifications for remote user %s:%s: %s via FCM devices, %s via APNs devices",
        server.uuid,
        user_identity,
        len(android_devices),
        len(apple_devices),
    )

    # Truncate incoming pushes to 200, due to APNs maximum message
    # sizes; see handle_remove_push_notification for the version of
    # this for notifications generated natively on the server.  We
    # apply this to remote-server pushes in case they predate that
    # commit.
    def truncate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        MAX_MESSAGE_IDS = 200
        if payload and payload.get("event") == "remove" and payload.get("zulip_message_ids"):
            ids = [int(id) for id in payload["zulip_message_ids"].split(",")]
            truncated_ids = sorted(ids)[-MAX_MESSAGE_IDS:]
            payload["zulip_message_ids"] = ",".join(str(id) for id in truncated_ids)
        return payload

    # The full request must complete within 30s, the timeout set by
    # Zulip remote hosts for push notification requests (see
    # PushBouncerSession).  The timeouts in the FCM and APNS codepaths
    # must be set accordingly; see send_android_push_notification and
    # send_apple_push_notification.

    gcm_payload = truncate_payload(gcm_payload)
    send_android_push_notification(
        user_identity, android_devices, gcm_payload, gcm_options, remote=server
    )

    if isinstance(apns_payload.get("custom"), dict) and isinstance(
        apns_payload["custom"].get("zulip"), dict
    ):
        apns_payload["custom"]["zulip"] = truncate_payload(apns_payload["custom"]["zulip"])
    send_apple_push_notification(user_identity, apple_devices, apns_payload, remote=server)

    return json_success(
        request,
        data={
            "total_android_devices": len(android_devices),
            "total_apple_devices": len(apple_devices),
        },
    )


def validate_incoming_table_data(
    server: RemoteZulipServer, model: Any, rows: List[Dict[str, Any]], is_count_stat: bool = False
) -> None:
    last_id = get_last_id_from_server(server, model)
    for row in rows:
        if is_count_stat and row["property"] not in COUNT_STATS:
            raise JsonableError(_("Invalid property {}").format(row["property"]))
        if row["id"] <= last_id:
            raise JsonableError(_("Data is out of order."))
        last_id = row["id"]


ModelT = TypeVar("ModelT", bound=Model)


def batch_create_table_data(
    server: RemoteZulipServer,
    model: Type[ModelT],
    row_objects: List[ModelT],
) -> None:
    BATCH_SIZE = 1000
    while len(row_objects) > 0:
        try:
            model.objects.bulk_create(row_objects[:BATCH_SIZE])
        except IntegrityError:
            logging.warning(
                "Invalid data saving %s for server %s/%s",
                model._meta.db_table,
                server.hostname,
                server.uuid,
            )
            raise JsonableError(_("Invalid data."))
        row_objects = row_objects[BATCH_SIZE:]


@has_request_variables
def remote_server_post_analytics(
    request: HttpRequest,
    server: RemoteZulipServer,
    realm_counts: List[Dict[str, Any]] = REQ(
        json_validator=check_list(
            check_dict_only(
                [
                    ("property", check_string),
                    ("realm", check_int),
                    ("id", check_int),
                    ("end_time", check_float),
                    ("subgroup", check_none_or(check_string)),
                    ("value", check_int),
                ]
            )
        )
    ),
    installation_counts: List[Dict[str, Any]] = REQ(
        json_validator=check_list(
            check_dict_only(
                [
                    ("property", check_string),
                    ("id", check_int),
                    ("end_time", check_float),
                    ("subgroup", check_none_or(check_string)),
                    ("value", check_int),
                ]
            )
        )
    ),
    realmauditlog_rows: Optional[List[Dict[str, Any]]] = REQ(
        json_validator=check_list(
            check_dict_only(
                [
                    ("id", check_int),
                    ("realm", check_int),
                    ("event_time", check_float),
                    ("backfilled", check_bool),
                    ("extra_data", check_none_or(check_string)),
                    ("event_type", check_int),
                ]
            )
        ),
        default=None,
    ),
) -> HttpResponse:
    validate_incoming_table_data(server, RemoteRealmCount, realm_counts, True)
    validate_incoming_table_data(server, RemoteInstallationCount, installation_counts, True)
    if realmauditlog_rows is not None:
        validate_incoming_table_data(server, RemoteRealmAuditLog, realmauditlog_rows)

    remote_realm_counts = [
        RemoteRealmCount(
            property=row["property"],
            realm_id=row["realm"],
            remote_id=row["id"],
            server=server,
            end_time=datetime.datetime.fromtimestamp(row["end_time"], tz=datetime.timezone.utc),
            subgroup=row["subgroup"],
            value=row["value"],
        )
        for row in realm_counts
    ]
    batch_create_table_data(server, RemoteRealmCount, remote_realm_counts)

    remote_installation_counts = [
        RemoteInstallationCount(
            property=row["property"],
            remote_id=row["id"],
            server=server,
            end_time=datetime.datetime.fromtimestamp(row["end_time"], tz=datetime.timezone.utc),
            subgroup=row["subgroup"],
            value=row["value"],
        )
        for row in installation_counts
    ]
    batch_create_table_data(server, RemoteInstallationCount, remote_installation_counts)

    if realmauditlog_rows is not None:
        remote_realm_audit_logs = [
            RemoteRealmAuditLog(
                realm_id=row["realm"],
                remote_id=row["id"],
                server=server,
                event_time=datetime.datetime.fromtimestamp(
                    row["event_time"], tz=datetime.timezone.utc
                ),
                backfilled=row["backfilled"],
                extra_data=row["extra_data"],
                event_type=row["event_type"],
            )
            for row in realmauditlog_rows
        ]
        batch_create_table_data(server, RemoteRealmAuditLog, remote_realm_audit_logs)

    return json_success(request)


def get_last_id_from_server(server: RemoteZulipServer, model: Any) -> int:
    last_count = model.objects.filter(server=server).order_by("remote_id").last()
    if last_count is not None:
        return last_count.remote_id
    return 0


@has_request_variables
def remote_server_check_analytics(request: HttpRequest, server: RemoteZulipServer) -> HttpResponse:
    result = {
        "last_realm_count_id": get_last_id_from_server(server, RemoteRealmCount),
        "last_installation_count_id": get_last_id_from_server(server, RemoteInstallationCount),
        "last_realmauditlog_id": get_last_id_from_server(server, RemoteRealmAuditLog),
    }
    return json_success(request, data=result)
