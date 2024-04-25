# See https://zulip.readthedocs.io/en/latest/subsystems/notifications.html

import asyncio
import base64
import copy
import logging
import re
from dataclasses import dataclass
from email.headerregistry import Address
from functools import cache
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

import gcm
import lxml.html
import orjson
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from typing_extensions import TypeAlias, override

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.actions.realm_settings import (
    do_set_push_notifications_enabled_end_timestamp,
    do_set_realm_property,
)
from zerver.lib.avatar import absolute_avatar_url, get_avatar_for_inaccessible_user
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.emoji_utils import hex_codepoint_to_emoji
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.message import access_message_and_usermessage, huddle_users
from zerver.lib.notification_data import get_mentioned_user_group
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.remote_server import (
    record_push_notifications_recently_working,
    send_json_to_push_bouncer,
    send_server_data_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.soft_deactivation import soft_reactivate_if_personal_notification
from zerver.lib.tex import change_katex_to_raw_latex
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.users import check_can_access_user
from zerver.models import (
    AbstractPushDeviceToken,
    ArchivedMessage,
    Message,
    PushDeviceToken,
    Realm,
    Recipient,
    Stream,
    UserMessage,
    UserProfile,
)
from zerver.models.realms import get_fake_email_domain
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.users import get_user_profile_by_id

if TYPE_CHECKING:
    import aioapns

logger = logging.getLogger(__name__)

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemotePushDeviceToken, RemoteZulipServer

DeviceToken: TypeAlias = Union[PushDeviceToken, "RemotePushDeviceToken"]


# We store the token as b64, but apns-client wants hex strings
def b64_to_hex(data: str) -> str:
    return base64.b64decode(data).hex()


def hex_to_b64(data: str) -> str:
    return base64.b64encode(bytes.fromhex(data)).decode()


def get_message_stream_name_from_database(message: Message) -> str:
    """
    Never use this function outside of the push-notifications
    codepath. Most of our code knows how to get streams
    up front in a more efficient manner.
    """
    stream_id = message.recipient.type_id
    return Stream.objects.get(id=stream_id).name


class UserPushIdentityCompat:
    """Compatibility class for supporting the transition from remote servers
    sending their UserProfile ids to the bouncer to sending UserProfile uuids instead.

    Until we can drop support for receiving user_id, we need this
    class, because a user's identity in the push notification context
    may be represented either by an id or uuid.
    """

    def __init__(self, user_id: Optional[int] = None, user_uuid: Optional[str] = None) -> None:
        assert user_id is not None or user_uuid is not None
        self.user_id = user_id
        self.user_uuid = user_uuid

    def filter_q(self) -> Q:
        """
        This aims to support correctly querying for RemotePushDeviceToken.
        If only one of (user_id, user_uuid) is provided, the situation is trivial,
        If both are provided, we want to query for tokens matching EITHER the
        uuid or the id - because the user may have devices with old registrations,
        so user_id-based, as well as new registration with uuid. Notifications
        naturally should be sent to both.
        """
        if self.user_id is not None and self.user_uuid is None:
            return Q(user_id=self.user_id)
        elif self.user_uuid is not None and self.user_id is None:
            return Q(user_uuid=self.user_uuid)
        else:
            assert self.user_id is not None and self.user_uuid is not None
            return Q(user_uuid=self.user_uuid) | Q(user_id=self.user_id)

    @override
    def __str__(self) -> str:
        result = ""
        if self.user_id is not None:
            result += f"<id:{self.user_id}>"
        if self.user_uuid is not None:
            result += f"<uuid:{self.user_uuid}>"

        return result

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, UserPushIdentityCompat):
            return self.user_id == other.user_id and self.user_uuid == other.user_uuid
        return False


#
# Sending to APNs, for iOS
#


@dataclass
class APNsContext:
    apns: "aioapns.APNs"
    loop: asyncio.AbstractEventLoop


def has_apns_credentials() -> bool:
    return settings.APNS_TOKEN_KEY_FILE is not None or settings.APNS_CERT_FILE is not None


@cache
def get_apns_context() -> Optional[APNsContext]:
    # We lazily do this import as part of optimizing Zulip's base
    # import time.
    import aioapns

    if not has_apns_credentials():  # nocoverage
        return None

    # NB if called concurrently, this will make excess connections.
    # That's a little sloppy, but harmless unless a server gets
    # hammered with a ton of these all at once after startup.
    loop = asyncio.new_event_loop()

    # Defining a no-op error-handling function overrides the default
    # behaviour of logging at ERROR level whenever delivery fails; we
    # handle those errors by checking the result in
    # send_apple_push_notification.
    async def err_func(
        request: aioapns.NotificationRequest, result: aioapns.common.NotificationResult
    ) -> None:
        pass  # nocoverage

    async def make_apns() -> aioapns.APNs:
        return aioapns.APNs(
            client_cert=settings.APNS_CERT_FILE,
            key=settings.APNS_TOKEN_KEY_FILE,
            key_id=settings.APNS_TOKEN_KEY_ID,
            team_id=settings.APNS_TEAM_ID,
            max_connection_attempts=APNS_MAX_RETRIES,
            use_sandbox=settings.APNS_SANDBOX,
            err_func=err_func,
            # The actual APNs topic will vary between notifications,
            # so we set it there, overriding any value we put here.
            # We can't just leave this out, though, because then
            # the constructor attempts to guess.
            topic="invalid.nonsense",
        )

    apns = loop.run_until_complete(make_apns())
    return APNsContext(apns=apns, loop=loop)


def modernize_apns_payload(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Take a payload in an unknown Zulip version's format, and return in current format."""
    # TODO this isn't super robust as is -- if a buggy remote server
    # sends a malformed payload, we are likely to raise an exception.
    if "message_ids" in data:
        # The format sent by 1.6.0, from the earliest pre-1.6.0
        # version with bouncer support up until 613d093d7 pre-1.7.0:
        #   'alert': str,              # just sender, and text about direct message/mention
        #   'message_ids': List[int],  # always just one
        return {
            "alert": data["alert"],
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": data["message_ids"],
                },
            },
        }
    else:
        # Something already compatible with the current format.
        # `alert` may be a string, or a dict with `title` and `body`.
        # In 1.7.0 and 1.7.1, before 0912b5ba8 pre-1.8.0, the only
        # item in `custom.zulip` is `message_ids`.
        return data


APNS_MAX_RETRIES = 3


def send_apple_push_notification(
    user_identity: UserPushIdentityCompat,
    devices: Sequence[DeviceToken],
    payload_data: Mapping[str, Any],
    remote: Optional["RemoteZulipServer"] = None,
) -> int:
    if not devices:
        return 0
    # We lazily do the APNS imports as part of optimizing Zulip's base
    # import time; since these are only needed in the push
    # notification queue worker, it's best to only import them in the
    # code that needs them.
    import aioapns
    import aioapns.exceptions

    apns_context = get_apns_context()
    if apns_context is None:
        logger.debug(
            "APNs: Dropping a notification because nothing configured.  "
            "Set PUSH_NOTIFICATION_BOUNCER_URL (or APNS_CERT_FILE)."
        )
        return 0

    if remote:
        assert settings.ZILENCER_ENABLED
        DeviceTokenClass: Type[AbstractPushDeviceToken] = RemotePushDeviceToken
    else:
        DeviceTokenClass = PushDeviceToken

    if remote:
        logger.info(
            "APNs: Sending notification for remote user %s:%s to %d devices",
            remote.uuid,
            user_identity,
            len(devices),
        )
    else:
        logger.info(
            "APNs: Sending notification for local user %s to %d devices",
            user_identity,
            len(devices),
        )
    payload_data = dict(modernize_apns_payload(payload_data))
    message = {**payload_data.pop("custom", {}), "aps": payload_data}

    have_missing_app_id = False
    for device in devices:
        if device.ios_app_id is None:
            # This should be present for all APNs tokens, as an invariant maintained
            # by the views that add the token to our database.
            logger.error(
                "APNs: Missing ios_app_id for user %s device %s", user_identity, device.token
            )
            have_missing_app_id = True
    if have_missing_app_id:
        devices = [device for device in devices if device.ios_app_id is not None]

    async def send_all_notifications() -> (
        Iterable[Tuple[DeviceToken, Union[aioapns.common.NotificationResult, BaseException]]]
    ):
        requests = [
            aioapns.NotificationRequest(
                apns_topic=device.ios_app_id,
                device_token=device.token,
                message=message,
                time_to_live=24 * 3600,
            )
            for device in devices
        ]
        results = await asyncio.gather(
            *(apns_context.apns.send_notification(request) for request in requests),
            return_exceptions=True,
        )
        return zip(devices, results)

    results = apns_context.loop.run_until_complete(send_all_notifications())

    successfully_sent_count = 0
    for device, result in results:
        if isinstance(result, aioapns.exceptions.ConnectionError):
            logger.error(
                "APNs: ConnectionError sending for user %s to device %s; check certificate expiration",
                user_identity,
                device.token,
            )
        elif isinstance(result, BaseException):
            logger.error(
                "APNs: Error sending for user %s to device %s",
                user_identity,
                device.token,
                exc_info=result,
            )
        elif result.is_successful:
            successfully_sent_count += 1
            logger.info(
                "APNs: Success sending for user %s to device %s", user_identity, device.token
            )
        elif result.description in ["Unregistered", "BadDeviceToken", "DeviceTokenNotForTopic"]:
            logger.info(
                "APNs: Removing invalid/expired token %s (%s)", device.token, result.description
            )
            # We remove all entries for this token (There
            # could be multiple for different Zulip servers).
            DeviceTokenClass._default_manager.filter(
                token=device.token, kind=DeviceTokenClass.APNS
            ).delete()
        else:
            logger.warning(
                "APNs: Failed to send for user %s to device %s: %s",
                user_identity,
                device.token,
                result.description,
            )

    return successfully_sent_count


#
# Sending to GCM, for Android
#


class FCMSession(OutgoingSession):
    def __init__(self) -> None:
        # We don't set up retries, since the gcm package does that for us.
        super().__init__(role="fcm", timeout=5)


def make_gcm_client() -> gcm.GCM:  # nocoverage
    # From GCM upstream's doc for migrating to FCM:
    #
    #   FCM supports HTTP and XMPP protocols that are virtually
    #   identical to the GCM server protocols, so you don't need to
    #   update your sending logic for the migration.
    #
    #   https://developers.google.com/cloud-messaging/android/android-migrate-fcm
    #
    # The one thing we're required to change on the server is the URL of
    # the endpoint.  So we get to keep using the GCM client library we've
    # been using (as long as we're happy with it) -- just monkey-patch in
    # that one change, because the library's API doesn't anticipate that
    # as a customization point.
    gcm.gcm.GCM_URL = "https://fcm.googleapis.com/fcm/send"
    return gcm.GCM(settings.ANDROID_GCM_API_KEY)


if settings.ANDROID_GCM_API_KEY:  # nocoverage
    gcm_client = make_gcm_client()
else:
    gcm_client = None


def has_gcm_credentials() -> bool:  # nocoverage
    return gcm_client is not None


# This is purely used in testing
def send_android_push_notification_to_user(
    user_profile: UserProfile, data: Dict[str, Any], options: Dict[str, Any]
) -> None:
    devices = list(PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.GCM))
    send_android_push_notification(
        UserPushIdentityCompat(user_id=user_profile.id), devices, data, options
    )


def parse_gcm_options(options: Dict[str, Any], data: Dict[str, Any]) -> str:
    """
    Parse GCM options, supplying defaults, and raising an error if invalid.

    The options permitted here form part of the Zulip notification
    bouncer's API.  They are:

    `priority`: Passed through to GCM; see upstream doc linked below.
        Zulip servers should always set this; when unset, we guess a value
        based on the behavior of old server versions.

    Including unrecognized options is an error.

    For details on options' semantics, see this GCM upstream doc:
      https://firebase.google.com/docs/cloud-messaging/http-server-ref

    Returns `priority`.
    """
    priority = options.pop("priority", None)
    if priority is None:
        # An older server.  Identify if this seems to be an actual notification.
        if data.get("event") == "message":
            priority = "high"
        else:  # `'event': 'remove'`, presumably
            priority = "normal"
    if priority not in ("normal", "high"):
        raise JsonableError(
            _(
                "Invalid GCM option to bouncer: priority {priority!r}",
            ).format(priority=priority)
        )

    if options:
        # We're strict about the API; there is no use case for a newer Zulip
        # server talking to an older bouncer, so we only need to provide
        # one-way compatibility.
        raise JsonableError(
            _(
                "Invalid GCM options to bouncer: {options}",
            ).format(options=orjson.dumps(options).decode())
        )

    return priority  # when this grows a second option, can make it a tuple


def send_android_push_notification(
    user_identity: UserPushIdentityCompat,
    devices: Sequence[DeviceToken],
    data: Dict[str, Any],
    options: Dict[str, Any],
    remote: Optional["RemoteZulipServer"] = None,
) -> int:
    """
    Send a GCM message to the given devices.

    See https://firebase.google.com/docs/cloud-messaging/http-server-ref
    for the GCM upstream API which this talks to.

    data: The JSON object (decoded) to send as the 'data' parameter of
        the GCM message.
    options: Additional options to control the GCM message sent.
        For details, see `parse_gcm_options`.
    """
    if not devices:
        return 0
    if not gcm_client:
        logger.debug(
            "Skipping sending a GCM push notification since "
            "PUSH_NOTIFICATION_BOUNCER_URL and ANDROID_GCM_API_KEY are both unset"
        )
        return 0

    if remote:
        logger.info(
            "GCM: Sending notification for remote user %s:%s to %d devices",
            remote.uuid,
            user_identity,
            len(devices),
        )
    else:
        logger.info(
            "GCM: Sending notification for local user %s to %d devices", user_identity, len(devices)
        )
    reg_ids = [device.token for device in devices]
    priority = parse_gcm_options(options, data)
    try:
        # See https://firebase.google.com/docs/cloud-messaging/http-server-ref .
        # Two kwargs `retries` and `session` get eaten by `json_request`;
        # the rest pass through to the GCM server.
        #
        # One initial request plus 2 retries, with 5-second timeouts,
        # and expected 1 + 2 seconds (the gcm module jitters its
        # backoff by ±50%, so worst case * 1.5) between them, totals
        # 18s expected, up to 19.5s worst case.
        res = gcm_client.json_request(
            registration_ids=reg_ids,
            priority=priority,
            data=data,
            retries=2,
            session=FCMSession(),
        )
    except OSError:
        logger.warning("Error while pushing to GCM", exc_info=True)
        return 0

    successfully_sent_count = 0
    if res and "success" in res:
        for reg_id, msg_id in res["success"].items():
            logger.info("GCM: Sent %s as %s", reg_id, msg_id)
        successfully_sent_count = len(res["success"].keys())

    if remote:
        assert settings.ZILENCER_ENABLED
        DeviceTokenClass: Type[AbstractPushDeviceToken] = RemotePushDeviceToken
    else:
        DeviceTokenClass = PushDeviceToken

    # res.canonical will contain results when there are duplicate registrations for the same
    # device. The "canonical" registration is the latest registration made by the device.
    # Ref: https://developer.android.com/google/gcm/adv.html#canonical
    if "canonical" in res:
        for reg_id, new_reg_id in res["canonical"].items():
            if reg_id == new_reg_id:
                # I'm not sure if this should happen. In any case, not really actionable.
                logger.warning("GCM: Got canonical ref but it already matches our ID %s!", reg_id)
            elif not DeviceTokenClass._default_manager.filter(
                token=new_reg_id, kind=DeviceTokenClass.GCM
            ).exists():
                # This case shouldn't happen; any time we get a canonical ref it should have been
                # previously registered in our system.
                #
                # That said, recovery is easy: just update the current PDT object to use the new ID.
                logger.warning(
                    "GCM: Got canonical ref %s replacing %s but new ID not registered! Updating.",
                    new_reg_id,
                    reg_id,
                )
                DeviceTokenClass._default_manager.filter(
                    token=reg_id, kind=DeviceTokenClass.GCM
                ).update(token=new_reg_id)
            else:
                # Since we know the new ID is registered in our system we can just drop the old one.
                logger.info("GCM: Got canonical ref %s, dropping %s", new_reg_id, reg_id)

                DeviceTokenClass._default_manager.filter(
                    token=reg_id, kind=DeviceTokenClass.GCM
                ).delete()

    if "errors" in res:
        for error, reg_ids in res["errors"].items():
            if error in ["NotRegistered", "InvalidRegistration"]:
                for reg_id in reg_ids:
                    logger.info("GCM: Removing %s", reg_id)
                    # We remove all entries for this token (There
                    # could be multiple for different Zulip servers).
                    DeviceTokenClass._default_manager.filter(
                        token=reg_id, kind=DeviceTokenClass.GCM
                    ).delete()
            else:
                for reg_id in reg_ids:
                    logger.warning("GCM: Delivery to %s failed: %s", reg_id, error)

    return successfully_sent_count

    # python-gcm handles retrying of the unsent messages.
    # Ref: https://github.com/geeknam/python-gcm/blob/master/gcm/gcm.py#L497


#
# Sending to a bouncer
#


def uses_notification_bouncer() -> bool:
    return settings.PUSH_NOTIFICATION_BOUNCER_URL is not None


def sends_notifications_directly() -> bool:
    return has_apns_credentials() and has_gcm_credentials() and not uses_notification_bouncer()


def send_notifications_to_bouncer(
    user_profile: UserProfile,
    apns_payload: Dict[str, Any],
    gcm_payload: Dict[str, Any],
    gcm_options: Dict[str, Any],
    android_devices: Sequence[DeviceToken],
    apple_devices: Sequence[DeviceToken],
) -> None:
    if len(android_devices) + len(apple_devices) == 0:
        logger.info(
            "Skipping contacting the bouncer for user %s because there are no registered devices",
            user_profile.id,
        )

        return

    post_data = {
        "user_uuid": str(user_profile.uuid),
        # user_uuid is the intended future format, but we also need to send user_id
        # to avoid breaking old mobile registrations, which were made with user_id.
        "user_id": user_profile.id,
        "realm_uuid": str(user_profile.realm.uuid),
        "apns_payload": apns_payload,
        "gcm_payload": gcm_payload,
        "gcm_options": gcm_options,
        "android_devices": [device.token for device in android_devices],
        "apple_devices": [device.token for device in apple_devices],
    }
    # Calls zilencer.views.remote_server_notify_push

    try:
        response_data = send_json_to_push_bouncer("POST", "push/notify", post_data)
    except PushNotificationsDisallowedByBouncerError as e:
        logger.warning("Bouncer refused to send push notification: %s", e.reason)
        do_set_realm_property(
            user_profile.realm,
            "push_notifications_enabled",
            False,
            acting_user=None,
        )
        do_set_push_notifications_enabled_end_timestamp(user_profile.realm, None, acting_user=None)
        return

    assert isinstance(response_data["total_android_devices"], int)
    assert isinstance(response_data["total_apple_devices"], int)

    assert isinstance(response_data["deleted_devices"], dict)
    assert isinstance(response_data["deleted_devices"]["android_devices"], list)
    assert isinstance(response_data["deleted_devices"]["apple_devices"], list)
    android_deleted_devices = response_data["deleted_devices"]["android_devices"]
    apple_deleted_devices = response_data["deleted_devices"]["apple_devices"]
    if android_deleted_devices or apple_deleted_devices:
        logger.info(
            "Deleting push tokens based on response from bouncer: Android: %s, Apple: %s",
            sorted(android_deleted_devices),
            sorted(apple_deleted_devices),
        )
        PushDeviceToken.objects.filter(
            kind=PushDeviceToken.GCM, token__in=android_deleted_devices
        ).delete()
        PushDeviceToken.objects.filter(
            kind=PushDeviceToken.APNS, token__in=apple_deleted_devices
        ).delete()

    total_android_devices, total_apple_devices = (
        response_data["total_android_devices"],
        response_data["total_apple_devices"],
    )
    do_increment_logging_stat(
        user_profile.realm,
        COUNT_STATS["mobile_pushes_sent::day"],
        None,
        timezone_now(),
        increment=total_android_devices + total_apple_devices,
    )

    remote_realm_dict = response_data.get("realm")
    if remote_realm_dict is not None:
        # The server may have updated our understanding of whether
        # push notifications will work.
        assert isinstance(remote_realm_dict, dict)
        can_push = remote_realm_dict["can_push"]
        do_set_realm_property(
            user_profile.realm,
            "push_notifications_enabled",
            can_push,
            acting_user=None,
        )
        do_set_push_notifications_enabled_end_timestamp(
            user_profile.realm, remote_realm_dict["expected_end_timestamp"], acting_user=None
        )
        if can_push:
            record_push_notifications_recently_working()

    logger.info(
        "Sent mobile push notifications for user %s through bouncer: %s via FCM devices, %s via APNs devices",
        user_profile.id,
        total_android_devices,
        total_apple_devices,
    )


#
# Managing device tokens
#


def add_push_device_token(
    user_profile: UserProfile, token_str: str, kind: int, ios_app_id: Optional[str] = None
) -> None:
    logger.info(
        "Registering push device: %d %r %d %r", user_profile.id, token_str, kind, ios_app_id
    )

    # Regardless of whether we're using the push notifications
    # bouncer, we want to store a PushDeviceToken record locally.
    # These can be used to discern whether the user has any mobile
    # devices configured, and is also where we will store encryption
    # keys for mobile push notifications.
    PushDeviceToken.objects.bulk_create(
        [
            PushDeviceToken(
                user_id=user_profile.id,
                token=token_str,
                kind=kind,
                ios_app_id=ios_app_id,
                # last_updated is to be renamed to date_created.
                last_updated=timezone_now(),
            ),
        ],
        ignore_conflicts=True,
    )

    if not uses_notification_bouncer():
        return

    # If we're sending things to the push notification bouncer
    # register this user with them here
    post_data = {
        "server_uuid": settings.ZULIP_ORG_ID,
        "user_uuid": str(user_profile.uuid),
        "realm_uuid": str(user_profile.realm.uuid),
        # user_id is sent so that the bouncer can delete any pre-existing registrations
        # for this user+device to avoid duplication upon adding the uuid registration.
        "user_id": str(user_profile.id),
        "token": token_str,
        "token_kind": kind,
    }

    if kind == PushDeviceToken.APNS:
        post_data["ios_app_id"] = ios_app_id

    logger.info("Sending new push device to bouncer: %r", post_data)
    # Calls zilencer.views.register_remote_push_device
    send_to_push_bouncer("POST", "push/register", post_data)


def remove_push_device_token(user_profile: UserProfile, token_str: str, kind: int) -> None:
    try:
        token = PushDeviceToken.objects.get(token=token_str, kind=kind, user=user_profile)
        token.delete()
    except PushDeviceToken.DoesNotExist:
        # If we are using bouncer, don't raise the exception. It will
        # be raised by the code below eventually. This is important
        # during the transition period after upgrading to a version
        # that stores local PushDeviceToken objects even when using
        # the push notifications bouncer.
        if not uses_notification_bouncer():
            raise JsonableError(_("Token does not exist"))

    # If we're sending things to the push notification bouncer
    # unregister this user with them here
    if uses_notification_bouncer():
        # TODO: Make this a remove item
        post_data = {
            "server_uuid": settings.ZULIP_ORG_ID,
            "realm_uuid": str(user_profile.realm.uuid),
            # We don't know here if the token was registered with uuid
            # or using the legacy id format, so we need to send both.
            "user_uuid": str(user_profile.uuid),
            "user_id": user_profile.id,
            "token": token_str,
            "token_kind": kind,
        }
        # Calls zilencer.views.unregister_remote_push_device
        send_to_push_bouncer("POST", "push/unregister", post_data)


def clear_push_device_tokens(user_profile_id: int) -> None:
    # Deletes all of a user's PushDeviceTokens.
    if uses_notification_bouncer():
        user_profile = get_user_profile_by_id(user_profile_id)
        user_uuid = str(user_profile.uuid)
        post_data = {
            "server_uuid": settings.ZULIP_ORG_ID,
            "realm_uuid": str(user_profile.realm.uuid),
            # We want to clear all registered token, and they may have
            # been registered with either uuid or id.
            "user_uuid": user_uuid,
            "user_id": user_profile_id,
        }
        send_to_push_bouncer("POST", "push/unregister/all", post_data)
        return

    PushDeviceToken.objects.filter(user_id=user_profile_id).delete()


#
# Push notifications in general
#


def push_notifications_configured() -> bool:
    """True just if this server has configured a way to send push notifications."""
    if (
        uses_notification_bouncer()
        and settings.ZULIP_ORG_KEY is not None
        and settings.ZULIP_ORG_ID is not None
    ):  # nocoverage
        # We have the needed configuration to send push notifications through
        # the bouncer.  Better yet would be to confirm that this config actually
        # works -- e.g., that we have ever successfully sent to the bouncer --
        # but this is a good start.
        return True
    if settings.DEVELOPMENT and (has_apns_credentials() or has_gcm_credentials()):  # nocoverage
        # Since much of the notifications logic is platform-specific, the mobile
        # developers often work on just one platform at a time, so we should
        # only require one to be configured.
        return True
    elif has_apns_credentials() and has_gcm_credentials():  # nocoverage
        # We have the needed configuration to send through APNs and GCM directly
        # (i.e., we are the bouncer, presumably.)  Again, assume it actually works.
        return True
    return False


def initialize_push_notifications() -> None:
    """Called during startup of the push notifications worker to check
    whether we expect mobile push notifications to work on this server
    and update state accordingly.
    """

    if sends_notifications_directly():
        # This server sends push notifications directly. Make sure we
        # are set to report to clients that push notifications are
        # enabled.
        for realm in Realm.objects.filter(push_notifications_enabled=False):
            do_set_realm_property(realm, "push_notifications_enabled", True, acting_user=None)
            do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)
        return

    if not push_notifications_configured():
        for realm in Realm.objects.filter(push_notifications_enabled=True):
            do_set_realm_property(realm, "push_notifications_enabled", False, acting_user=None)
            do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)
        if settings.DEVELOPMENT and not settings.TEST_SUITE:
            # Avoid unnecessary spam on development environment startup
            return  # nocoverage
        logger.warning(
            "Mobile push notifications are not configured.\n  "
            "See https://zulip.readthedocs.io/en/latest/"
            "production/mobile-push-notifications.html"
        )
        return

    if uses_notification_bouncer():
        # If we're using the notification bouncer, check if we can
        # actually send push notifications, and update our
        # understanding of that state for each realm accordingly.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        return

    logger.warning(  # nocoverage
        "Mobile push notifications are not fully configured.\n  "
        "See https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html"
    )
    for realm in Realm.objects.filter(push_notifications_enabled=True):  # nocoverage
        do_set_realm_property(realm, "push_notifications_enabled", False, acting_user=None)
        do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)


def get_mobile_push_content(rendered_content: str) -> str:
    def get_text(elem: lxml.html.HtmlElement) -> str:
        # Convert default emojis to their Unicode equivalent.
        classes = elem.get("class", "")
        if "emoji" in classes:
            match = re.search(r"emoji-(?P<emoji_code>\S+)", classes)
            if match:
                emoji_code = match.group("emoji_code")
                return hex_codepoint_to_emoji(emoji_code)
        # Handles realm emojis, avatars etc.
        if elem.tag == "img":
            return elem.get("alt", "")
        if elem.tag == "blockquote":
            return ""  # To avoid empty line before quote text
        return elem.text or ""

    def format_as_quote(quote_text: str) -> str:
        return "".join(
            f"> {line}\n"
            for line in quote_text.splitlines()
            if line  # Remove empty lines
        )

    def render_olist(ol: lxml.html.HtmlElement) -> str:
        items = []
        counter = int(ol.get("start")) if ol.get("start") else 1
        nested_levels = sum(1 for ancestor in ol.iterancestors("ol"))
        indent = ("\n" + "  " * nested_levels) if nested_levels else ""

        for li in ol:
            items.append(indent + str(counter) + ". " + process(li).strip())
            counter += 1

        return "\n".join(items)

    def render_spoiler(elem: lxml.html.HtmlElement) -> str:
        header = elem.find_class("spoiler-header")[0]
        text = process(header).strip()
        if len(text) == 0:
            return "(…)\n"
        return f"{text} (…)\n"

    def process(elem: lxml.html.HtmlElement) -> str:
        plain_text = ""
        if elem.tag == "ol":
            plain_text = render_olist(elem)
        elif "spoiler-block" in elem.get("class", ""):
            plain_text += render_spoiler(elem)
        else:
            plain_text = get_text(elem)
            sub_text = ""
            for child in elem:
                sub_text += process(child)
            if elem.tag == "blockquote":
                sub_text = format_as_quote(sub_text)
            plain_text += sub_text
            plain_text += elem.tail or ""
        return plain_text

    if settings.PUSH_NOTIFICATION_REDACT_CONTENT:
        return _("New message")

    elem = lxml.html.fragment_fromstring(rendered_content, create_parent=True)
    change_katex_to_raw_latex(elem)
    plain_text = process(elem)
    return plain_text


def truncate_content(content: str) -> Tuple[str, bool]:
    # We use Unicode character 'HORIZONTAL ELLIPSIS' (U+2026) instead
    # of three dots as this saves two extra characters for textual
    # content. This function will need to be updated to handle Unicode
    # combining characters and tags when we start supporting themself.
    if len(content) <= 200:
        return content, False
    return content[:200] + "…", True


def get_base_payload(user_profile: UserProfile) -> Dict[str, Any]:
    """Common fields for all notification payloads."""
    data: Dict[str, Any] = {}

    # These will let the app support logging into multiple realms and servers.
    data["server"] = settings.EXTERNAL_HOST
    data["realm_id"] = user_profile.realm.id
    data["realm_uri"] = user_profile.realm.uri
    data["realm_name"] = user_profile.realm.name
    data["user_id"] = user_profile.id

    return data


def get_message_payload(
    user_profile: UserProfile,
    message: Message,
    mentioned_user_group_id: Optional[int] = None,
    mentioned_user_group_name: Optional[str] = None,
    can_access_sender: bool = True,
) -> Dict[str, Any]:
    """Common fields for `message` payloads, for all platforms."""
    data = get_base_payload(user_profile)

    # `sender_id` is preferred, but some existing versions use `sender_email`.
    data["sender_id"] = message.sender.id
    if not can_access_sender:
        # A guest user can only receive a stream message from an
        # inaccessible user as we allow unsubscribed users to send
        # messages to streams. For direct messages, the guest gains
        # access to the user if they where previously inaccessible.
        data["sender_email"] = Address(
            username=f"user{message.sender.id}", domain=get_fake_email_domain(message.realm.host)
        ).addr_spec
    else:
        data["sender_email"] = message.sender.email

    data["time"] = datetime_to_timestamp(message.date_sent)
    if mentioned_user_group_id is not None:
        assert mentioned_user_group_name is not None
        data["mentioned_user_group_id"] = mentioned_user_group_id
        data["mentioned_user_group_name"] = mentioned_user_group_name

    if message.recipient.type == Recipient.STREAM:
        data["recipient_type"] = "stream"
        data["stream"] = get_message_stream_name_from_database(message)
        data["stream_id"] = message.recipient.type_id
        data["topic"] = message.topic_name()
    elif message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        data["recipient_type"] = "private"
        data["pm_users"] = huddle_users(message.recipient.id)
    else:  # Recipient.PERSONAL
        data["recipient_type"] = "private"

    return data


def get_apns_alert_title(message: Message) -> str:
    """
    On an iOS notification, this is the first bolded line.
    """
    if message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        recipients = get_display_recipient(message.recipient)
        assert isinstance(recipients, list)
        return ", ".join(sorted(r["full_name"] for r in recipients))
    elif message.is_stream_message():
        stream_name = get_message_stream_name_from_database(message)
        return f"#{stream_name} > {message.topic_name()}"
    # For 1:1 direct messages, we just show the sender name.
    return message.sender.full_name


def get_apns_alert_subtitle(
    message: Message,
    trigger: str,
    user_profile: UserProfile,
    mentioned_user_group_name: Optional[str] = None,
    can_access_sender: bool = True,
) -> str:
    """
    On an iOS notification, this is the second bolded line.
    """
    sender_name = message.sender.full_name
    if not can_access_sender:
        # A guest user can only receive a stream message from an
        # inaccessible user as we allow unsubscribed users to send
        # messages to streams. For direct messages, the guest gains
        # access to the user if they where previously inaccessible.
        sender_name = str(UserProfile.INACCESSIBLE_USER_NAME)

    if trigger == NotificationTriggers.MENTION:
        if mentioned_user_group_name is not None:
            return _("{full_name} mentioned @{user_group_name}:").format(
                full_name=sender_name, user_group_name=mentioned_user_group_name
            )
        else:
            return _("{full_name} mentioned you:").format(full_name=sender_name)
    elif trigger in (
        NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
        NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
        NotificationTriggers.TOPIC_WILDCARD_MENTION,
        NotificationTriggers.STREAM_WILDCARD_MENTION,
    ):
        return _("{full_name} mentioned everyone:").format(full_name=sender_name)
    elif message.recipient.type == Recipient.PERSONAL:
        return ""
    # For group direct messages, or regular messages to a stream,
    # just use a colon to indicate this is the sender.
    return sender_name + ":"


def get_apns_badge_count(
    user_profile: UserProfile, read_messages_ids: Optional[Sequence[int]] = []
) -> int:
    # NOTE: We have temporarily set get_apns_badge_count to always
    # return 0 until we can debug a likely mobile app side issue with
    # handling notifications while the app is open.
    return 0


def get_apns_badge_count_future(
    user_profile: UserProfile, read_messages_ids: Optional[Sequence[int]] = []
) -> int:
    # Future implementation of get_apns_badge_count; unused but
    # we expect to use this once we resolve client-side bugs.
    return (
        UserMessage.objects.filter(user_profile=user_profile)
        .extra(where=[UserMessage.where_active_push_notification()])
        .exclude(
            # If we've just marked some messages as read, they're still
            # marked as having active notifications; we'll clear that flag
            # only after we've sent that update to the devices.  So we need
            # to exclude them explicitly from the count.
            message_id__in=read_messages_ids
        )
        .count()
    )


def get_message_payload_apns(
    user_profile: UserProfile,
    message: Message,
    trigger: str,
    mentioned_user_group_id: Optional[int] = None,
    mentioned_user_group_name: Optional[str] = None,
    can_access_sender: bool = True,
) -> Dict[str, Any]:
    """A `message` payload for iOS, via APNs."""
    zulip_data = get_message_payload(
        user_profile, message, mentioned_user_group_id, mentioned_user_group_name, can_access_sender
    )
    zulip_data.update(
        message_ids=[message.id],
    )

    assert message.rendered_content is not None
    with override_language(user_profile.default_language):
        content, _ = truncate_content(get_mobile_push_content(message.rendered_content))
        apns_data = {
            "alert": {
                "title": get_apns_alert_title(message),
                "subtitle": get_apns_alert_subtitle(
                    message, trigger, user_profile, mentioned_user_group_name, can_access_sender
                ),
                "body": content,
            },
            "sound": "default",
            "badge": get_apns_badge_count(user_profile),
            "custom": {"zulip": zulip_data},
        }
    return apns_data


def get_message_payload_gcm(
    user_profile: UserProfile,
    message: Message,
    mentioned_user_group_id: Optional[int] = None,
    mentioned_user_group_name: Optional[str] = None,
    can_access_sender: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A `message` payload + options, for Android via GCM/FCM."""
    data = get_message_payload(
        user_profile, message, mentioned_user_group_id, mentioned_user_group_name, can_access_sender
    )

    if not can_access_sender:
        # A guest user can only receive a stream message from an
        # inaccessible user as we allow unsubscribed users to send
        # messages to streams. For direct messages, the guest gains
        # access to the user if they where previously inaccessible.
        sender_avatar_url = get_avatar_for_inaccessible_user()
        sender_name = str(UserProfile.INACCESSIBLE_USER_NAME)
    else:
        sender_avatar_url = absolute_avatar_url(message.sender)
        sender_name = message.sender.full_name

    assert message.rendered_content is not None
    with override_language(user_profile.default_language):
        content, truncated = truncate_content(get_mobile_push_content(message.rendered_content))
        data.update(
            event="message",
            zulip_message_id=message.id,  # message_id is reserved for CCS
            content=content,
            content_truncated=truncated,
            sender_full_name=sender_name,
            sender_avatar_url=sender_avatar_url,
        )
    gcm_options = {"priority": "high"}
    return data, gcm_options


def get_remove_payload_gcm(
    user_profile: UserProfile,
    message_ids: List[int],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A `remove` payload + options, for Android via GCM/FCM."""
    gcm_payload = get_base_payload(user_profile)
    gcm_payload.update(
        event="remove",
        zulip_message_ids=",".join(str(id) for id in message_ids),
        # Older clients (all clients older than 2019-02-13) look only at
        # `zulip_message_id` and ignore `zulip_message_ids`.  Do our best.
        zulip_message_id=message_ids[0],
    )
    gcm_options = {"priority": "normal"}
    return gcm_payload, gcm_options


def get_remove_payload_apns(user_profile: UserProfile, message_ids: List[int]) -> Dict[str, Any]:
    zulip_data = get_base_payload(user_profile)
    zulip_data.update(
        event="remove",
        zulip_message_ids=",".join(str(id) for id in message_ids),
    )
    apns_data = {
        "badge": get_apns_badge_count(user_profile, message_ids),
        "custom": {"zulip": zulip_data},
    }
    return apns_data


def handle_remove_push_notification(user_profile_id: int, message_ids: List[int]) -> None:
    """This should be called when a message that previously had a
    mobile push notification executed is read.  This triggers a push to the
    mobile app, when the message is read on the server, to remove the
    message from the notification.
    """
    if not push_notifications_configured():
        return

    user_profile = get_user_profile_by_id(user_profile_id)

    # We may no longer have access to the message here; for example,
    # the user (1) got a message, (2) read the message in the web UI,
    # and then (3) it was deleted.  When trying to send the push
    # notification for (2), after (3) has happened, there is no
    # message to fetch -- but we nonetheless want to remove the mobile
    # notification.  Because of this, verification of access to
    # the messages is skipped here.
    # Because of this, no access to the Message objects should be
    # done; they are treated as a list of opaque ints.

    # APNs has a 4KB limit on the maximum size of messages, which
    # translated to several hundred message IDs in one of these
    # notifications. In rare cases, it's possible for someone to mark
    # thousands of push notification eligible messages as read at
    # once. We could handle this situation with a loop, but we choose
    # to truncate instead to avoid extra network traffic, because it's
    # very likely the user has manually cleared the notifications in
    # their mobile device's UI anyway.
    #
    # When truncating, we keep only the newest N messages in this
    # remove event. This is optimal because older messages are the
    # ones most likely to have already been manually cleared at some
    # point in the past.
    #
    # We choose 200 here because a 10-digit message ID plus a comma and
    # space consume 12 bytes, and 12 x 200 = 2400 bytes is still well
    # below the 4KB limit (leaving plenty of space for metadata).
    MAX_APNS_MESSAGE_IDS = 200
    truncated_message_ids = sorted(message_ids)[-MAX_APNS_MESSAGE_IDS:]
    gcm_payload, gcm_options = get_remove_payload_gcm(user_profile, truncated_message_ids)
    apns_payload = get_remove_payload_apns(user_profile, truncated_message_ids)

    android_devices = list(
        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.GCM).order_by("id")
    )
    apple_devices = list(
        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.APNS).order_by("id")
    )
    if uses_notification_bouncer():
        send_notifications_to_bouncer(
            user_profile, apns_payload, gcm_payload, gcm_options, android_devices, apple_devices
        )
    else:
        user_identity = UserPushIdentityCompat(user_id=user_profile_id)

        android_successfully_sent_count = send_android_push_notification(
            user_identity, android_devices, gcm_payload, gcm_options
        )
        apple_successfully_sent_count = send_apple_push_notification(
            user_identity, apple_devices, apns_payload
        )

        do_increment_logging_stat(
            user_profile.realm,
            COUNT_STATS["mobile_pushes_sent::day"],
            None,
            timezone_now(),
            increment=android_successfully_sent_count + apple_successfully_sent_count,
        )

    # We intentionally use the non-truncated message_ids here.  We are
    # assuming in this very rare case that the user has manually
    # dismissed these notifications on the device side, and the server
    # should no longer track them as outstanding notifications.
    with transaction.atomic(savepoint=False):
        UserMessage.select_for_update_query().filter(
            user_profile_id=user_profile_id,
            message_id__in=message_ids,
        ).update(flags=F("flags").bitand(~UserMessage.flags.active_mobile_push_notification))


def handle_push_notification(user_profile_id: int, missed_message: Dict[str, Any]) -> None:
    """
    missed_message is the event received by the
    zerver.worker.missedmessage_mobile_notifications.PushNotificationWorker.consume function.
    """
    if not push_notifications_configured():
        return
    user_profile = get_user_profile_by_id(user_profile_id)

    if user_profile.is_bot:  # nocoverage
        # We don't expect to reach here for bot users. However, this code exists
        # to find and throw away any pre-existing events in the queue while
        # upgrading from versions before our notifiability logic was implemented.
        # TODO/compatibility: This block can be removed when one can no longer
        # upgrade from versions <= 4.0 to versions >= 5.0
        logger.warning(
            "Send-push-notification event found for bot user %s. Skipping.", user_profile_id
        )
        return

    if not (
        user_profile.enable_offline_push_notifications
        or user_profile.enable_online_push_notifications
    ):
        # BUG: Investigate why it's possible to get here.
        return  # nocoverage

    with transaction.atomic(savepoint=False):
        try:
            (message, user_message) = access_message_and_usermessage(
                user_profile, missed_message["message_id"], lock_message=True
            )
        except JsonableError:
            if ArchivedMessage.objects.filter(id=missed_message["message_id"]).exists():
                # If the cause is a race with the message being deleted,
                # that's normal and we have no need to log an error.
                return
            logging.info(
                "Unexpected message access failure handling push notifications: %s %s",
                user_profile.id,
                missed_message["message_id"],
            )
            return

        if user_message is not None:
            # If the user has read the message already, don't push-notify.
            if user_message.flags.read or user_message.flags.active_mobile_push_notification:
                return

            # Otherwise, we mark the message as having an active mobile
            # push notification, so that we can send revocation messages
            # later.
            user_message.flags.active_mobile_push_notification = True
            user_message.save(update_fields=["flags"])
        else:
            # Users should only be getting push notifications into this
            # queue for messages they haven't received if they're
            # long-term idle; anything else is likely a bug.
            if not user_profile.long_term_idle:
                logger.error(
                    "Could not find UserMessage with message_id %s and user_id %s",
                    missed_message["message_id"],
                    user_profile_id,
                    exc_info=True,
                )
                return

    trigger = missed_message["trigger"]

    # TODO/compatibility: Translation code for the rename of
    # `wildcard_mentioned` to `stream_wildcard_mentioned`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    if trigger == "wildcard_mentioned":
        trigger = NotificationTriggers.STREAM_WILDCARD_MENTION  # nocoverage

    # TODO/compatibility: Translation code for the rename of
    # `followed_topic_wildcard_mentioned` to `stream_wildcard_mentioned_in_followed_topic`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    if trigger == "followed_topic_wildcard_mentioned":
        trigger = NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC  # nocoverage

    # TODO/compatibility: Translation code for the rename of
    # `private_message` to `direct_message`. Remove this when
    # one can no longer directly upgrade from 7.x to main.
    if trigger == "private_message":
        trigger = NotificationTriggers.DIRECT_MESSAGE  # nocoverage

    # mentioned_user_group will be None if the user is personally mentioned
    # regardless whether they are a member of the mentioned user group in the
    # message or not.
    mentioned_user_group_id = None
    mentioned_user_group_name = None
    mentioned_user_group_members_count = None
    mentioned_user_group = get_mentioned_user_group([missed_message], user_profile)
    if mentioned_user_group is not None:
        mentioned_user_group_id = mentioned_user_group.id
        mentioned_user_group_name = mentioned_user_group.name
        mentioned_user_group_members_count = mentioned_user_group.members_count

    # Soft reactivate if pushing to a long_term_idle user that is personally mentioned
    soft_reactivate_if_personal_notification(
        user_profile, {trigger}, mentioned_user_group_members_count
    )

    if message.is_stream_message():
        # This will almost always be True. The corner case where you
        # can be receiving a message from a user you cannot access
        # involves your being a guest user whose access is restricted
        # by a can_access_all_users_group policy, and you can't access
        # the sender because they are sending a message to a public
        # stream that you are subscribed to but they are not.

        can_access_sender = check_can_access_user(message.sender, user_profile)
    else:
        # For private messages, the recipient will gain access
        # to the sender if they did not had access previously.
        can_access_sender = True

    apns_payload = get_message_payload_apns(
        user_profile,
        message,
        trigger,
        mentioned_user_group_id,
        mentioned_user_group_name,
        can_access_sender,
    )
    gcm_payload, gcm_options = get_message_payload_gcm(
        user_profile, message, mentioned_user_group_id, mentioned_user_group_name, can_access_sender
    )
    logger.info("Sending push notifications to mobile clients for user %s", user_profile_id)

    android_devices = list(
        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.GCM).order_by("id")
    )

    apple_devices = list(
        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.APNS).order_by("id")
    )
    if uses_notification_bouncer():
        send_notifications_to_bouncer(
            user_profile, apns_payload, gcm_payload, gcm_options, android_devices, apple_devices
        )
        return

    logger.info(
        "Sending mobile push notifications for local user %s: %s via FCM devices, %s via APNs devices",
        user_profile_id,
        len(android_devices),
        len(apple_devices),
    )
    user_identity = UserPushIdentityCompat(user_id=user_profile.id)

    apple_successfully_sent_count = send_apple_push_notification(
        user_identity, apple_devices, apns_payload
    )
    android_successfully_sent_count = send_android_push_notification(
        user_identity, android_devices, gcm_payload, gcm_options
    )

    do_increment_logging_stat(
        user_profile.realm,
        COUNT_STATS["mobile_pushes_sent::day"],
        None,
        timezone_now(),
        increment=apple_successfully_sent_count + android_successfully_sent_count,
    )


def send_test_push_notification_directly_to_devices(
    user_identity: UserPushIdentityCompat,
    devices: Sequence[DeviceToken],
    base_payload: Dict[str, Any],
    remote: Optional["RemoteZulipServer"] = None,
) -> None:
    payload = copy.deepcopy(base_payload)
    payload["event"] = "test"

    apple_devices = [device for device in devices if device.kind == PushDeviceToken.APNS]
    android_devices = [device for device in devices if device.kind == PushDeviceToken.GCM]
    # Let's make the payloads separate objects to make sure mutating to make e.g. Android
    # adjustments doesn't affect the Apple payload and vice versa.
    apple_payload = copy.deepcopy(payload)
    android_payload = copy.deepcopy(payload)

    realm_uri = base_payload["realm_uri"]
    realm_name = base_payload["realm_name"]
    apns_data = {
        "alert": {
            "title": _("Test notification"),
            "body": _("This is a test notification from {realm_name} ({realm_uri}).").format(
                realm_name=realm_name, realm_uri=realm_uri
            ),
        },
        "sound": "default",
        "custom": {"zulip": apple_payload},
    }
    send_apple_push_notification(user_identity, apple_devices, apns_data, remote=remote)

    android_payload["time"] = datetime_to_timestamp(timezone_now())
    gcm_options = {"priority": "high"}
    send_android_push_notification(
        user_identity, android_devices, android_payload, gcm_options, remote=remote
    )


def send_test_push_notification(user_profile: UserProfile, devices: List[PushDeviceToken]) -> None:
    base_payload = get_base_payload(user_profile)
    if uses_notification_bouncer():
        for device in devices:
            post_data = {
                "realm_uuid": str(user_profile.realm.uuid),
                "user_uuid": str(user_profile.uuid),
                "user_id": user_profile.id,
                "token": device.token,
                "token_kind": device.kind,
                "base_payload": base_payload,
            }

            logger.info("Sending test push notification to bouncer: %r", post_data)
            send_json_to_push_bouncer("POST", "push/test_notification", post_data)

        return

    # This server doesn't need the bouncer, so we send directly to the device.
    user_identity = UserPushIdentityCompat(
        user_id=user_profile.id, user_uuid=str(user_profile.uuid)
    )
    send_test_push_notification_directly_to_devices(
        user_identity, devices, base_payload, remote=None
    )


class InvalidPushDeviceTokenError(JsonableError):
    code = ErrorCode.INVALID_PUSH_DEVICE_TOKEN

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Device not recognized")


class InvalidRemotePushDeviceTokenError(JsonableError):
    code = ErrorCode.INVALID_REMOTE_PUSH_DEVICE_TOKEN

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Device not recognized by the push bouncer")


class PushNotificationsDisallowedByBouncerError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
