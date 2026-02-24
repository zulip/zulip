import asyncio
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from aioapns import NotificationRequest
from django.utils.timezone import now as timezone_now
from firebase_admin import exceptions as firebase_exceptions
from firebase_admin import messaging as firebase_messaging
from firebase_admin.messaging import UnregisteredError as FCMUnregisteredError

from zerver.lib.devices import b64decode_token_id_base64, b64encode_token_id_int
from zerver.lib.push_notifications import (
    APNsPushRequest,
    FCMPushRequest,
    SendNotificationResponseData,
    fcm_app,
    get_apns_context,
    get_info_from_apns_result,
)
from zerver.models.realms import Realm
from zilencer.models import RemotePushDevice, RemoteRealm

logger = logging.getLogger(__name__)


@dataclass
class SentPushNotificationResult:
    successfully_sent_count: int
    delete_token_ids_base64: list[str]


def send_e2ee_push_notification_apple(
    apns_requests: list[NotificationRequest],
    apns_remote_push_devices: list[RemotePushDevice],
    log_context: str,
) -> SentPushNotificationResult:
    import aioapns

    successfully_sent_count = 0
    delete_token_ids_base64: list[str] = []
    apns_context = get_apns_context()

    if apns_context is None:
        logger.error(
            "APNs: Dropping push notifications since "
            "neither APNS_TOKEN_KEY_FILE nor APNS_CERT_FILE is set."
        )
        return SentPushNotificationResult(
            successfully_sent_count=successfully_sent_count,
            delete_token_ids_base64=delete_token_ids_base64,
        )

    async def send_all_notifications() -> Iterable[
        tuple[RemotePushDevice, aioapns.common.NotificationResult | BaseException]
    ]:
        results = await asyncio.gather(
            *(apns_context.apns.send_notification(request) for request in apns_requests),
            return_exceptions=True,
        )
        return zip(apns_remote_push_devices, results, strict=False)

    results = apns_context.loop.run_until_complete(send_all_notifications())

    for remote_push_device, result in results:
        log_context = log_context % remote_push_device.token
        result_info = get_info_from_apns_result(
            result,
            remote_push_device,
            log_context,
        )

        if result_info.successfully_sent:
            successfully_sent_count += 1
        elif result_info.delete_token_id_base64 is not None:
            remote_push_device.expired_time = timezone_now()
            remote_push_device.save(update_fields=["expired_time"])
            delete_token_ids_base64.append(result_info.delete_token_id_base64)

    return SentPushNotificationResult(
        successfully_sent_count=successfully_sent_count,
        delete_token_ids_base64=delete_token_ids_base64,
    )


def send_e2ee_push_notification_android(
    fcm_requests: list[firebase_messaging.Message],
    fcm_remote_push_devices: list[RemotePushDevice],
    log_context: str,
) -> SentPushNotificationResult:
    successfully_sent_count = 0
    delete_token_ids_base64: list[str] = []

    if fcm_app is None:
        logger.error("FCM: Dropping push notifications since ANDROID_FCM_CREDENTIALS_PATH is unset")
        return SentPushNotificationResult(
            successfully_sent_count=successfully_sent_count,
            delete_token_ids_base64=delete_token_ids_base64,
        )

    try:
        batch_response = firebase_messaging.send_each(fcm_requests, app=fcm_app)
    except firebase_exceptions.FirebaseError:
        logger.warning("Error while pushing to FCM", exc_info=True)
        return SentPushNotificationResult(
            successfully_sent_count=successfully_sent_count,
            delete_token_ids_base64=delete_token_ids_base64,
        )

    for idx, response in enumerate(batch_response.responses):
        # We enumerate to have idx to track which token the response
        # corresponds to. send_each() preserves the order of the messages,
        # so this works.

        remote_push_device = fcm_remote_push_devices[idx]
        token = remote_push_device.token
        log_context = log_context % token

        if response.success:
            successfully_sent_count += 1
            logger.info("FCM: Sent message with ID: %s %s", response.message_id, log_context)
        else:
            error = response.exception
            if isinstance(error, FCMUnregisteredError):
                remote_push_device.expired_time = timezone_now()
                remote_push_device.save(update_fields=["expired_time"])
                delete_token_ids_base64.append(b64encode_token_id_int(remote_push_device.token_id))

                logger.info("FCM: Removing %s due to %s", token, error.code)
            else:
                logger.warning(
                    "FCM: Delivery failed %s: %s:%s",
                    log_context,
                    error.__class__,
                    error,
                )

    return SentPushNotificationResult(
        successfully_sent_count=successfully_sent_count,
        delete_token_ids_base64=delete_token_ids_base64,
    )


def send_e2ee_push_notifications(
    push_requests: list[APNsPushRequest | FCMPushRequest],
    *,
    realm: Realm | None = None,
    remote_realm: RemoteRealm | None = None,
) -> SendNotificationResponseData:
    assert (realm is None) ^ (remote_realm is None)

    import aioapns

    token_ids_base64 = set()
    token_ids_int = set()
    for push_request in push_requests:
        token_ids_base64.add(push_request.token_id)
        token_ids_int.add(b64decode_token_id_base64(push_request.token_id))

    remote_push_devices = RemotePushDevice.objects.filter(
        token_id__in=token_ids_int,
        realm=realm,
        remote_realm=remote_realm,
        expired_time__isnull=True,
    )
    token_id_base64_to_remote_push_device = {
        b64encode_token_id_int(remote_push_device.token_id): remote_push_device
        for remote_push_device in remote_push_devices
    }
    unexpired_token_ids_base64 = set(token_id_base64_to_remote_push_device.keys())

    # Token IDs which should be deleted on server.
    # Either the token ID is invalid or the token
    # associated has been marked invalid/expired by APNs/FCM.
    delete_token_ids_base64 = list(
        filter(
            lambda token_id_base64: token_id_base64 not in unexpired_token_ids_base64,
            token_ids_base64,
        )
    )

    apns_requests = []
    apns_remote_push_devices: list[RemotePushDevice] = []

    fcm_requests = []
    fcm_remote_push_devices: list[RemotePushDevice] = []

    for push_request in push_requests:
        token_id_base64 = push_request.token_id
        if token_id_base64 not in unexpired_token_ids_base64:
            continue

        remote_push_device = token_id_base64_to_remote_push_device[token_id_base64]
        if remote_push_device.token_kind == RemotePushDevice.TokenKind.APNS:
            assert isinstance(push_request, APNsPushRequest)
            apns_requests.append(
                aioapns.NotificationRequest(
                    apns_topic=remote_push_device.ios_app_id,
                    device_token=remote_push_device.token,
                    message=asdict(push_request.payload),
                    priority=push_request.http_headers.apns_priority,
                    push_type=push_request.http_headers.apns_push_type,
                )
            )
            apns_remote_push_devices.append(remote_push_device)
        else:
            assert isinstance(push_request, FCMPushRequest)
            fcm_payload = dict(
                # FCM only allows string values, so we stringify push_key_id.
                push_key_id=str(push_request.payload.push_key_id),
                encrypted_data=push_request.payload.encrypted_data,
            )
            fcm_requests.append(
                firebase_messaging.Message(
                    data=fcm_payload,
                    token=remote_push_device.token,
                    android=firebase_messaging.AndroidConfig(priority=push_request.fcm_priority),
                )
            )
            fcm_remote_push_devices.append(remote_push_device)

    if realm is not None:
        log_context = f"to (realm={realm.uuid}, device=%s)"
    else:
        assert remote_realm is not None
        log_context = f"to (remote_realm={remote_realm.uuid}, device=%s)"

    apple_successfully_sent_count = 0
    if len(apns_requests) > 0:
        sent_push_notification_result = send_e2ee_push_notification_apple(
            apns_requests,
            apns_remote_push_devices,
            log_context,
        )
        apple_successfully_sent_count = sent_push_notification_result.successfully_sent_count
        delete_token_ids_base64.extend(sent_push_notification_result.delete_token_ids_base64)

    android_successfully_sent_count = 0
    if len(fcm_requests) > 0:
        sent_push_notification_result = send_e2ee_push_notification_android(
            fcm_requests,
            fcm_remote_push_devices,
            log_context,
        )
        android_successfully_sent_count = sent_push_notification_result.successfully_sent_count
        delete_token_ids_base64.extend(sent_push_notification_result.delete_token_ids_base64)

    return {
        "apple_successfully_sent_count": apple_successfully_sent_count,
        "android_successfully_sent_count": android_successfully_sent_count,
        "delete_token_ids": delete_token_ids_base64,
    }
