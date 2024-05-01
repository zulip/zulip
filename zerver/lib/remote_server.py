import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
from urllib.parse import urljoin

import orjson
import requests
from django.conf import settings
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import UUID4, BaseModel, ConfigDict, Field, Json, field_validator

from analytics.lib.counts import LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
from analytics.models import InstallationCount, RealmCount
from version import API_FEATURE_LEVEL, ZULIP_VERSION
from zerver.actions.realm_settings import (
    do_set_push_notifications_enabled_end_timestamp,
    do_set_realm_property,
)
from zerver.lib import redis_utils
from zerver.lib.exceptions import (
    JsonableError,
    MissingRemoteRealmError,
    RemoteRealmServerMismatchError,
)
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.redis_utils import get_redis_client
from zerver.models import Realm, RealmAuditLog
from zerver.models.realms import OrgTypeEnum

redis_client = get_redis_client()


class PushBouncerSession(OutgoingSession):
    def __init__(self, timeout: int = 15) -> None:
        super().__init__(role="push_bouncer", timeout=timeout)


class PushNotificationBouncerError(Exception):
    pass


class PushNotificationBouncerRetryLaterError(JsonableError):
    http_status_code = 502


class PushNotificationBouncerServerError(PushNotificationBouncerRetryLaterError):
    http_status_code = 502


class RealmCountDataForAnalytics(BaseModel):
    property: str
    realm: int
    id: int
    end_time: float
    subgroup: Optional[str]
    value: int


class InstallationCountDataForAnalytics(BaseModel):
    property: str
    id: int
    end_time: float
    subgroup: Optional[str]
    value: int


class RealmAuditLogDataForAnalytics(BaseModel):
    id: int
    realm: int
    event_time: float
    backfilled: bool
    extra_data: Optional[Union[str, Dict[str, Any]]]
    event_type: int


class RealmDataForAnalytics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    host: str
    url: str
    name: str = ""
    org_type: int = 0
    date_created: float
    deactivated: bool
    is_system_bot_realm: bool = False

    authentication_methods: Dict[str, bool] = Field(default_factory=dict)

    uuid: UUID4
    uuid_owner_secret: str

    @field_validator("org_type")
    @classmethod
    def check_is_allowed_value(cls, value: int) -> int:
        if value not in [org_type.value for org_type in OrgTypeEnum]:
            raise ValueError("Not a valid org_type value")

        return value


class AnalyticsRequest(BaseModel):
    realm_counts: Json[List[RealmCountDataForAnalytics]]
    installation_counts: Json[List[InstallationCountDataForAnalytics]]
    realmauditlog_rows: Optional[Json[List[RealmAuditLogDataForAnalytics]]] = None
    realms: Json[List[RealmDataForAnalytics]]
    version: Optional[Json[str]]
    api_feature_level: Optional[Json[int]]


class UserDataForRemoteBilling(BaseModel):
    uuid: UUID4
    email: str
    full_name: str


def send_to_push_bouncer(
    method: str,
    endpoint: str,
    post_data: Union[bytes, Mapping[str, Union[str, int, None, bytes]]],
    extra_headers: Mapping[str, str] = {},
) -> Dict[str, object]:
    """While it does actually send the notice, this function has a lot of
    code and comments around error handling for the push notifications
    bouncer.  There are several classes of failures, each with its own
    potential solution:

    * Network errors with requests.request.  We raise an exception to signal
      it to the callers.

    * 500 errors from the push bouncer or other unexpected responses;
      we don't try to parse the response, but do make clear the cause.

    * 400 errors from the push bouncer.  Here there are 2 categories:
      Our server failed to connect to the push bouncer (should throw)
      vs. client-side errors like an invalid token.

    """
    assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
    assert settings.ZULIP_ORG_ID is not None
    assert settings.ZULIP_ORG_KEY is not None
    url = urljoin(settings.PUSH_NOTIFICATION_BOUNCER_URL, "/api/v1/remotes/" + endpoint)
    api_auth = requests.auth.HTTPBasicAuth(settings.ZULIP_ORG_ID, settings.ZULIP_ORG_KEY)

    headers = {"User-agent": f"ZulipServer/{ZULIP_VERSION}"}
    headers.update(extra_headers)

    if endpoint == "server/analytics":
        # Uploading audit log and/or analytics data can require the
        # bouncer to do a significant chunk of work in a few
        # situations; since this occurs in background jobs, set a long
        # timeout.
        session = PushBouncerSession(timeout=90)
    else:
        session = PushBouncerSession()

    try:
        res = session.request(
            method,
            url,
            data=post_data,
            auth=api_auth,
            verify=True,
            headers=headers,
        )
    except (
        requests.exceptions.Timeout,
        requests.exceptions.SSLError,
        requests.exceptions.ConnectionError,
    ) as e:
        raise PushNotificationBouncerRetryLaterError(
            f"{type(e).__name__} while trying to connect to push notification bouncer"
        )

    if res.status_code >= 500:
        # 5xx's should be resolved by the people who run the push
        # notification bouncer service, and they'll get an appropriate
        # error notification from the server. We raise an exception to signal
        # to the callers that the attempt failed and they can retry.
        error_msg = f"Received {res.status_code} from push notification bouncer"
        logging.warning(error_msg)
        raise PushNotificationBouncerServerError(error_msg)
    elif res.status_code >= 400:
        # If JSON parsing errors, just let that exception happen
        result_dict = orjson.loads(res.content)
        msg = result_dict["msg"]
        if "code" in result_dict and result_dict["code"] == "INVALID_ZULIP_SERVER":
            # Invalid Zulip server credentials should email this server's admins
            raise PushNotificationBouncerError(
                _("Push notifications bouncer error: {error}").format(error=msg)
            )
        elif "code" in result_dict and result_dict["code"] == "PUSH_NOTIFICATIONS_DISALLOWED":
            from zerver.lib.push_notifications import PushNotificationsDisallowedByBouncerError

            raise PushNotificationsDisallowedByBouncerError(reason=msg)
        elif (
            endpoint == "push/test_notification"
            and "code" in result_dict
            and result_dict["code"] == "INVALID_REMOTE_PUSH_DEVICE_TOKEN"
        ):
            # This error from the notification debugging endpoint should just be directly
            # communicated to the device.
            # TODO: Extend this to use a more general mechanism when we add more such error responses.
            from zerver.lib.push_notifications import InvalidRemotePushDeviceTokenError

            raise InvalidRemotePushDeviceTokenError
        elif (
            endpoint == "server/billing"
            and "code" in result_dict
            and result_dict["code"] == "MISSING_REMOTE_REALM"
        ):  # nocoverage
            # The callers requesting this endpoint want the exception to propagate
            # so they can catch it.
            raise MissingRemoteRealmError
        elif (
            endpoint == "server/billing"
            and "code" in result_dict
            and result_dict["code"] == "REMOTE_REALM_SERVER_MISMATCH_ERROR"
        ):  # nocoverage
            # The callers requesting this endpoint want the exception to propagate
            # so they can catch it.
            raise RemoteRealmServerMismatchError
        else:
            # But most other errors coming from the push bouncer
            # server are client errors (e.g. never-registered token)
            # and should be handled as such.
            raise JsonableError(msg)
    elif res.status_code != 200:
        # Anything else is unexpected and likely suggests a bug in
        # this version of Zulip, so we throw an exception that will
        # email the server admins.
        raise PushNotificationBouncerError(
            f"Push notification bouncer returned unexpected status code {res.status_code}"
        )

    # If we don't throw an exception, it's a successful bounce!
    return orjson.loads(res.content)


def send_json_to_push_bouncer(
    method: str, endpoint: str, post_data: Mapping[str, object]
) -> Dict[str, object]:
    return send_to_push_bouncer(
        method,
        endpoint,
        orjson.dumps(post_data),
        extra_headers={"Content-type": "application/json"},
    )


PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY = "push_notifications_recently_working_ts"


def record_push_notifications_recently_working() -> None:
    # Record the timestamp in redis, marking that push notifications
    # were working as of this moment.

    redis_key = redis_utils.REDIS_KEY_PREFIX + PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY
    # Keep this record around for 24h in case it's useful for debugging.
    redis_client.set(redis_key, str(timezone_now().timestamp()), ex=60 * 60 * 24)


def check_push_notifications_recently_working() -> bool:
    # Check in redis whether push notifications were working in the last hour.
    redis_key = redis_utils.REDIS_KEY_PREFIX + PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY
    timestamp = redis_client.get(redis_key)
    if timestamp is None:
        return False

    # If the timestamp is within the last hour, we consider push notifications to be working.
    return timezone_now().timestamp() - float(timestamp) < 60 * 60


def maybe_mark_pushes_disabled(
    e: Union[JsonableError, orjson.JSONDecodeError], logger: logging.Logger
) -> None:
    if isinstance(e, PushNotificationBouncerServerError):
        # We don't fall through and deactivate the flag, since this is
        # not under the control of the caller.
        return

    if isinstance(e, JsonableError):
        logger.warning(e.msg)
    else:
        logger.exception("Exception communicating with %s", settings.PUSH_NOTIFICATION_BOUNCER_URL)

    # An exception was thrown talking to the push bouncer. There may
    # be certain transient failures that we could ignore here -
    # therefore we check whether push notifications were recently working
    # and if so, the error can be treated as transient.
    # Otherwise, the assumed explanation is that there is something wrong
    # either with our credentials being corrupted or our ability to reach the
    # bouncer service over the network, so we move to
    # reporting push notifications as likely not working.
    if check_push_notifications_recently_working():
        # Push notifications were recently observed working, so we
        # assume this is likely a transient failure.
        return

    for realm in Realm.objects.filter(push_notifications_enabled=True):
        do_set_realm_property(realm, "push_notifications_enabled", False, acting_user=None)
        do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)


def build_analytics_data(
    realm_count_query: QuerySet[RealmCount],
    installation_count_query: QuerySet[InstallationCount],
    realmauditlog_query: QuerySet[RealmAuditLog],
) -> Tuple[
    List[RealmCountDataForAnalytics],
    List[InstallationCountDataForAnalytics],
    List[RealmAuditLogDataForAnalytics],
]:
    # We limit the batch size on the client side to avoid OOM kills timeouts, etc.
    MAX_CLIENT_BATCH_SIZE = 10000
    realm_count_data = [
        RealmCountDataForAnalytics(
            property=row.property,
            realm=row.realm.id,
            id=row.id,
            end_time=row.end_time.timestamp(),
            subgroup=row.subgroup,
            value=row.value,
        )
        for row in realm_count_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]
    installation_count_data = [
        InstallationCountDataForAnalytics(
            property=row.property,
            id=row.id,
            end_time=row.end_time.timestamp(),
            subgroup=row.subgroup,
            value=row.value,
        )
        for row in installation_count_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]
    zerver_realmauditlog = [
        RealmAuditLogDataForAnalytics(
            id=row.id,
            realm=row.realm.id,
            event_time=row.event_time.timestamp(),
            backfilled=row.backfilled,
            # Note that we don't need to add extra_data_json here because
            # the view remote_server_post_analytics populates extra_data_json
            # from the provided extra_data.
            extra_data=row.extra_data,
            event_type=row.event_type,
        )
        for row in realmauditlog_query.order_by("id")[0:MAX_CLIENT_BATCH_SIZE]
    ]

    return realm_count_data, installation_count_data, zerver_realmauditlog


def get_realms_info_for_push_bouncer(realm_id: Optional[int] = None) -> List[RealmDataForAnalytics]:
    realms = Realm.objects.order_by("id")
    if realm_id is not None:  # nocoverage
        realms = realms.filter(id=realm_id)

    realm_info_list = [
        RealmDataForAnalytics(
            id=realm.id,
            uuid=realm.uuid,
            uuid_owner_secret=realm.uuid_owner_secret,
            host=realm.host,
            url=realm.uri,
            deactivated=realm.deactivated,
            date_created=realm.date_created.timestamp(),
            org_type=realm.org_type,
            name=realm.name,
            authentication_methods=realm.authentication_methods_dict(),
            is_system_bot_realm=realm.string_id == settings.SYSTEM_BOT_REALM,
        )
        for realm in realms
    ]

    return realm_info_list


def send_server_data_to_push_bouncer(consider_usage_statistics: bool = True) -> None:
    logger = logging.getLogger("zulip.analytics")
    # first, check what's latest
    try:
        result = send_to_push_bouncer("GET", "server/analytics/status", {})
    except (JsonableError, orjson.JSONDecodeError) as e:
        maybe_mark_pushes_disabled(e, logger)
        return

    # Gather only entries with IDs greater than the last ID received by the push bouncer.
    # We don't re-send old data that's already been submitted.
    last_acked_realm_count_id = result["last_realm_count_id"]
    last_acked_installation_count_id = result["last_installation_count_id"]
    last_acked_realmauditlog_id = result["last_realmauditlog_id"]

    if settings.SUBMIT_USAGE_STATISTICS and consider_usage_statistics:
        # Only upload usage statistics, which is relatively expensive,
        # if called from the analytics cron job and the server has
        # uploading such statistics enabled.
        installation_count_query = InstallationCount.objects.filter(
            id__gt=last_acked_installation_count_id
        ).exclude(property__in=LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER)
        realm_count_query = RealmCount.objects.filter(id__gt=last_acked_realm_count_id).exclude(
            property__in=LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
        )
    else:
        installation_count_query = InstallationCount.objects.none()
        realm_count_query = RealmCount.objects.none()

    (realm_count_data, installation_count_data, realmauditlog_data) = build_analytics_data(
        realm_count_query=realm_count_query,
        installation_count_query=installation_count_query,
        realmauditlog_query=RealmAuditLog.objects.filter(
            event_type__in=RealmAuditLog.SYNCED_BILLING_EVENTS, id__gt=last_acked_realmauditlog_id
        ),
    )

    record_count = len(realm_count_data) + len(installation_count_data) + len(realmauditlog_data)
    request = AnalyticsRequest.model_construct(
        realm_counts=realm_count_data,
        installation_counts=installation_count_data,
        realmauditlog_rows=realmauditlog_data,
        realms=get_realms_info_for_push_bouncer(),
        version=ZULIP_VERSION,
        api_feature_level=API_FEATURE_LEVEL,
    )

    # Send the actual request, and process the response.
    try:
        response = send_to_push_bouncer(
            "POST", "server/analytics", request.model_dump(round_trip=True)
        )
    except (JsonableError, orjson.JSONDecodeError) as e:
        maybe_mark_pushes_disabled(e, logger)
        return

    assert isinstance(response["realms"], dict)  # for mypy
    realms = response["realms"]
    for realm_uuid, data in realms.items():
        try:
            realm = Realm.objects.get(uuid=realm_uuid)
        except Realm.DoesNotExist:
            # This occurs if the installation's database was rebuilt
            # from scratch or a realm was hard-deleted from the local
            # database, after generating secrets and talking to the
            # bouncer.
            logger.warning("Received unexpected realm UUID from bouncer %s", realm_uuid)
            continue

        do_set_realm_property(
            realm, "push_notifications_enabled", data["can_push"], acting_user=None
        )
        do_set_push_notifications_enabled_end_timestamp(
            realm, data["expected_end_timestamp"], acting_user=None
        )

    logger.info("Reported %d records", record_count)


def maybe_enqueue_audit_log_upload(realm: Realm) -> None:
    # Update the push notifications service, either with the fact that
    # the realm now exists or updates to its audit log of users.
    #
    # Done via a queue worker so that networking failures cannot have
    # any impact on the success operation of the local server's
    # ability to do operations that trigger these updates.
    from zerver.lib.push_notifications import uses_notification_bouncer

    if uses_notification_bouncer():
        event = {"type": "push_bouncer_update_for_realm", "realm_id": realm.id}
        queue_event_on_commit("deferred_work", event)
