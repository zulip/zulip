from zerver.models import UserProfile
from zerver.models.push_notifications import PushDevice
from zerver.tornado.django_api import send_event_on_commit


def do_register_push_device(
    user_profile: UserProfile, push_account_id: int, token_kind: str, push_key_bytes: bytes
) -> None:
    PushDevice.objects.update_or_create(
        user=user_profile,
        push_account_id=push_account_id,
        defaults={"token_kind": token_kind, "push_key": push_key_bytes, "error_code": None},
    )

    event = dict(
        type="push_device",
        push_account_id=push_account_id,
        status="pending",
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
