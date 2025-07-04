import logging
import random
import time
from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.exceptions import (
    InvalidBouncerPublicKeyError,
    PushRegistrationLivenessTimedOutError,
)
from zerver.lib.push_notifications import PUSH_REGISTRATION_LIVENESS_TIMEOUT
from zerver.lib.remote_server import send_to_push_bouncer
from zerver.models import PushDevice
from zerver.models.users import UserProfile, get_user_profile_by_id
from zerver.tornado.django_api import send_event_on_commit
from zerver.worker.base import QueueProcessingWorker, assign_queue

if settings.ZILENCER_ENABLED:
    from zilencer.views import do_register_remote_push_device

logger = logging.getLogger(__name__)


@assign_queue("register_push_device_to_bouncer")
class RegisterPushDeviceToBouncerWorker(QueueProcessingWorker):
    @staticmethod
    def handle_liveness_timedout(user_profile: UserProfile, push_account_id: int) -> None:
        PushDevice.objects.filter(user=user_profile, push_account_id=push_account_id).delete()
        event = dict(
            type="push_account",
            op="remove",
            push_account_id=str(push_account_id),
        )
        send_event_on_commit(user_profile.realm, event, [user_profile.id])

        logging.error(
            "Push device registration for user_id=%s, push_account_id=%s timedout.",
            user_profile.id,
            push_account_id,
        )

    @override
    def consume(self, event: dict[str, Any]) -> None:
        user_profile_id: int = event["user_profile_id"]
        user_profile = get_user_profile_by_id(user_profile_id)
        bouncer_public_key: str = event["bouncer_public_key"]
        encrypted_push_registration: str = event["encrypted_push_registration"]
        push_account_id: int = event["push_account_id"]

        attempt = 1
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
                    result = send_to_push_bouncer("POST", "push/e2ee/register", post_data)
                    assert isinstance(result["device_id"], int)  # for mypy
                    device_id = result["device_id"]
                # If successful, break out of the retry loop.
                break
            except InvalidBouncerPublicKeyError:
                PushDevice.objects.filter(
                    user=user_profile, push_account_id=push_account_id
                ).delete()
                event = dict(
                    type="push_account",
                    op="remove",
                    push_account_id=str(push_account_id),
                    reason="Invalid bouncer_public_key",
                )
                send_event_on_commit(user_profile.realm, event, [user_profile.id])
                return
            except PushRegistrationLivenessTimedOutError:
                self.handle_liveness_timedout(user_profile, push_account_id)
                return
            except Exception as e:
                logging.warning(e)
                # Exponential backoff with jitter.
                retry_delay_secs = min(2**attempt, 90) + random.uniform(0, 1)
                time.sleep(retry_delay_secs)
                attempt += 1
                continue  # retry
        else:
            self.handle_liveness_timedout(user_profile, push_account_id)
            return

        # Registration successful. Clear 'encrypted_push_registration'
        # and 'bouncer_public_key' as they are no longer of use.
        assert device_id is not None
        PushDevice.objects.filter(user=user_profile, push_account_id=push_account_id).update(
            bouncer_device_id=device_id,
            encrypted_push_registration=None,
            bouncer_public_key=None,
        )
        event = dict(
            type="push_account",
            op="update",
            push_account_id=str(push_account_id),
            status="active",
        )
        send_event_on_commit(user_profile.realm, event, [user_profile.id])
