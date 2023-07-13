from typing import IO, Dict, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.emoji import get_emoji_file_name
from zerver.lib.exceptions import JsonableError
from zerver.lib.pysa import mark_sanitized
from zerver.lib.upload import upload_emoji_image
from zerver.models import (
    EmojiInfo,
    Realm,
    RealmAuditLog,
    RealmEmoji,
    UserProfile,
    active_user_ids,
    get_all_custom_emoji_for_realm,
)
from zerver.tornado.django_api import send_event_on_commit


def notify_realm_emoji(realm: Realm, realm_emoji: Dict[str, EmojiInfo]) -> None:
    event = dict(type="realm_emoji", op="update", realm_emoji=realm_emoji)
    send_event_on_commit(realm, event, active_user_ids(realm.id))


def check_add_realm_emoji(
    realm: Realm, name: str, author: UserProfile, image_file: IO[bytes]
) -> RealmEmoji:
    try:
        realm_emoji = RealmEmoji(realm=realm, name=name, author=author)
        realm_emoji.full_clean()
        realm_emoji.save()
    except (IntegrityError, ValidationError):
        # Match the string in upload_emoji.
        raise JsonableError(_("A custom emoji with this name already exists."))

    emoji_file_name = get_emoji_file_name(image_file.name, realm_emoji.id)

    # The only user-controlled portion of 'emoji_file_name' is an extension,
    # which can not contain '..' or '/' or '\', making it difficult to exploit
    emoji_file_name = mark_sanitized(emoji_file_name)

    emoji_uploaded_successfully = False
    is_animated = False
    try:
        is_animated = upload_emoji_image(image_file, emoji_file_name, author)
        emoji_uploaded_successfully = True
    finally:
        if not emoji_uploaded_successfully:
            realm_emoji.delete()
    realm_emoji.file_name = emoji_file_name
    realm_emoji.is_animated = is_animated
    realm_emoji.save(update_fields=["file_name", "is_animated"])

    realm_emoji_dict = get_all_custom_emoji_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=author,
        event_type=RealmAuditLog.REALM_EMOJI_ADDED,
        event_time=timezone_now(),
        extra_data={
            "realm_emoji": dict(sorted(realm_emoji_dict.items())),
            "added_emoji": realm_emoji_dict[str(realm_emoji.id)],
        },
    )
    notify_realm_emoji(realm_emoji.realm, realm_emoji_dict)
    return realm_emoji


@transaction.atomic(durable=True)
def do_remove_realm_emoji(realm: Realm, name: str, *, acting_user: Optional[UserProfile]) -> None:
    emoji = RealmEmoji.objects.get(realm=realm, name=name, deactivated=False)
    emoji.deactivated = True
    emoji.save(update_fields=["deactivated"])

    realm_emoji_dict = get_all_custom_emoji_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_EMOJI_REMOVED,
        event_time=timezone_now(),
        extra_data={
            "realm_emoji": dict(sorted(realm_emoji_dict.items())),
            "deactivated_emoji": realm_emoji_dict[str(emoji.id)],
        },
    )

    notify_realm_emoji(realm, realm_emoji_dict)
