import logging
from typing import TypedDict

from django.conf import settings

from zerver.lib.exceptions import (
    InvalidBouncerPublicKeyError,
    InvalidEncryptedPushRegistrationError,
    JsonableError,
    MissingRemoteRealmError,
    RequestExpiredError,
)
from zerver.lib.push_notifications import PushNotificationsDisallowedByBouncerError
from zerver.lib.remote_server import (
    PushNotificationBouncerError,
    PushNotificationBouncerRetryLaterError,
    PushNotificationBouncerServerError,
    send_to_push_bouncer,
)
from zerver.models import PushDevice
from zerver.models.users import UserProfile, get_user_profile_by_id
from zerver.tornado.django_api import send_event_on_commit

if settings.ZILENCER_ENABLED:
    from zilencer.views import do_register_remote_push_device

logger = logging.getLogger(__name__)


class RegisterPushDeviceToBouncerQueueItem(TypedDict):
    user_profile_id: int
    bouncer_public_key: str
    encrypted_push_registration: str
    push_account_id: int


def handle_registration_to_bouncer_failure(
    user_profile: UserProfile, push_account_id: int, error_code: str
) -> None:
    """Handles a failed registration request to the bouncer by
    notifying or preparing to notify clients.

    * Sends a `push_device` event to notify online clients immediately.

    * Stores the `error_code` in the `PushDevice` table. This is later
      used, along with other metadata, to notify offline clients the
      next time they call `/register`. See the `push_devices` field in
      the `/register` response.
    """
    PushDevice.objects.filter(user=user_profile, push_account_id=push_account_id).update(
        error_code=error_code
    )
    event = dict(
        type="push_device",
        push_account_id=str(push_account_id),
        status="failed",
        error_code=error_code,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])

    # Report the `REQUEST_EXPIRED_ERROR` to the server admins as it indicates
    # a long-lasting outage somewhere between the server and the bouncer,
    # most likely in either the server or its local network configuration.
    if error_code == PushDevice.ErrorCode.REQUEST_EXPIRED:
        logging.error(
            "Push device registration request for user_id=%s, push_account_id=%s expired.",
            user_profile.id,
            push_account_id,
        )


def handle_register_push_device_to_bouncer(
    queue_item: RegisterPushDeviceToBouncerQueueItem,
) -> None:
    user_profile_id = queue_item["user_profile_id"]
    user_profile = get_user_profile_by_id(user_profile_id)
    bouncer_public_key = queue_item["bouncer_public_key"]
    encrypted_push_registration = queue_item["encrypted_push_registration"]
    push_account_id = queue_item["push_account_id"]

    try:
        if settings.ZILENCER_ENABLED:
            device_id = do_register_remote_push_device(
                bouncer_public_key,
                encrypted_push_registration,
                push_account_id,
                realm=user_profile.realm,
            )
        else:
            post_data: dict[str, str | int] = {
                "realm_uuid": str(user_profile.realm.uuid),
                "push_account_id": push_account_id,
                "encrypted_push_registration": encrypted_push_registration,
                "bouncer_public_key": bouncer_public_key,
            }
            result = send_to_push_bouncer("POST", "push/e2ee/register", post_data)
            assert isinstance(result["device_id"], int)  # for mypy
            device_id = result["device_id"]
    except (
        PushNotificationBouncerRetryLaterError,
        PushNotificationBouncerServerError,
    ) as e:  # nocoverage
        # Network error or 5xx error response from bouncer server.
        # Keep retrying to register until `RequestExpiredError` is raised.
        raise PushNotificationBouncerRetryLaterError(e.msg)
    except (
        # Need to resubmit realm info - `manage.py register_server`
        MissingRemoteRealmError,
        # Invalid credentials or unexpected status code
        PushNotificationBouncerError,
        # Plan doesn't allow sending push notifications
        PushNotificationsDisallowedByBouncerError,
    ):
        # Server admins need to fix these set of errors, report them.
        # Server should keep retrying to register until `RequestExpiredError` is raised.
        error_msg = f"Push device registration request for user_id={user_profile.id}, push_account_id={push_account_id} failed."
        logging.error(error_msg)
        raise PushNotificationBouncerRetryLaterError(error_msg)
    except (
        InvalidBouncerPublicKeyError,
        InvalidEncryptedPushRegistrationError,
        RequestExpiredError,
        # Any future or unexpected exceptions that we add.
        JsonableError,
    ) as e:
        handle_registration_to_bouncer_failure(
            user_profile, push_account_id, error_code=e.__class__.code.name
        )
        return

    # Registration successful.
    PushDevice.objects.filter(user=user_profile, push_account_id=push_account_id).update(
        bouncer_device_id=device_id
    )
    event = dict(
        type="push_device",
        push_account_id=str(push_account_id),
        status="active",
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
