import logging
import time
from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.exceptions import (
    MissingBouncerPublicKeyError,
    PushRegistrationLifespanExceededError,
)
from zerver.lib.push_notifications import PUSH_REGISTRATION_LIVENESS_TIMEOUT
from zerver.lib.remote_server import send_to_push_bouncer
from zerver.models import PushDevice
from zerver.models.users import get_user_profile_by_id
from zerver.tornado.django_api import send_event_on_commit
from zerver.worker.base import QueueProcessingWorker, assign_queue

if settings.ZILENCER_ENABLED:
    from zilencer.views import do_register_remote_push_device

logger = logging.getLogger(__name__)


@assign_queue("register_push_device_to_bouncer")
class RegisterPushDeviceToBouncerWorker(QueueProcessingWorker):
    @override
    def consume(self, event: dict[str, Any]) -> None:
        user_profile_id: int = event["user_profile_id"]
        user_profile = get_user_profile_by_id(user_profile_id)
        bouncer_public_key: str = event["bouncer_public_key"]
        encrypted_push_registration: str = event["encrypted_push_registration"]
        push_account_id: int = event["push_account_id"]

        device_id = None
        start_time = time.time()
        while time.time() - start_time < PUSH_REGISTRATION_LIVENESS_TIMEOUT:
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
                        "user_uuid": str(user_profile.uuid),
                        "realm_uuid": str(user_profile.realm.uuid),
                        "push_account_id": push_account_id,
                        "encrypted_push_registration": encrypted_push_registration,
                        "bouncer_public_key": bouncer_public_key,
                    }
                    result = send_to_push_bouncer("POST", "push/e2ee/register/", post_data)
                    assert isinstance(result["device_id"], int)  # for mypy
                    device_id = result["device_id"]
                # If successful, break out of the retry loop.
                break
            except MissingBouncerPublicKeyError:
                PushDevice.objects.filter(
                    user=user_profile, push_account_id=push_account_id
                ).delete()
                event = dict(
                    type="push_account_registration_status",
                    op="remove",
                    push_account_id=push_account_id,
                    reason="Invalid bouncer_public_key",
                )
                send_event_on_commit(user_profile.realm, event, [user_profile.id])
                return
            except PushRegistrationLifespanExceededError:
                PushDevice.objects.filter(
                    user=user_profile, push_account_id=push_account_id
                ).delete()
                # TODO: Log error + Send an email to admin.
                event = dict(
                    type="push_account_registration_status",
                    op="remove",
                    push_account_id=push_account_id,
                )
                send_event_on_commit(user_profile.realm, event, [user_profile.id])
                return
            except Exception as e:
                logging.warning("Unexpected error during push registration: %s", str(e))
                continue  # retry
        else:
            # TODO: Log error + Send an email to admin.
            event = dict(
                type="push_account_registration_status",
                op="remove",
                push_account_id=push_account_id,
            )
            send_event_on_commit(user_profile.realm, event, [user_profile.id])
            return

        assert device_id is not None
        PushDevice.objects.filter(user=user_profile, push_account_id=push_account_id).update(
            bouncer_device_id=device_id,
            encrypted_push_registration=None,
            bouncer_public_key=None,
        )
        event = dict(
            type="push_account_registration_status",
            op="update",
            push_account_id=push_account_id,
            status="active",
        )
        send_event_on_commit(user_profile.realm, event, [user_profile.id])
