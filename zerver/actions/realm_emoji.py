from typing import IO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.emoji import get_emoji_file_name
from zerver.lib.exceptions import JsonableError
from zerver.lib.mime_types import INLINE_MIME_TYPES
from zerver.lib.thumbnail import THUMBNAIL_ACCEPT_IMAGE_TYPES, BadImageError
from zerver.lib.upload import upload_emoji_image
from zerver.models import Realm, RealmAuditLog, RealmEmoji, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realm_emoji import EmojiInfo, get_all_custom_emoji_for_realm
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


def notify_realm_emoji(realm: Realm, realm_emoji: dict[str, EmojiInfo]) -> None:
    event = dict(type="realm_emoji", op="update", realm_emoji=realm_emoji)
    send_event_on_commit(realm, event, active_user_ids(realm.id))


@transaction.atomic(durable=True)
def check_add_realm_emoji(
    realm: Realm, name: str, author: UserProfile, image_file: IO[bytes], content_type: str
) -> RealmEmoji:
    try:
        realm_emoji = RealmEmoji(realm=realm, name=name, author=author)
        realm_emoji.full_clean()
        realm_emoji.save()
    except (IntegrityError, ValidationError):
        # This exists to handle races; upload_emoji checked prior to
        # calling, and also hand-validated the name, but we're now in
        # a transaction.  The error string should match the one in
        # upload_emoji.
        raise JsonableError(_("A custom emoji with this name already exists."))

    # This mirrors the check in upload_emoji_image because we want to
    # have some reasonable guarantees on the content-type before
    # deriving the file extension from it.
    if content_type not in THUMBNAIL_ACCEPT_IMAGE_TYPES or content_type not in INLINE_MIME_TYPES:
        raise BadImageError(_("Invalid image format"))

    emoji_file_name = get_emoji_file_name(content_type, realm_emoji.id)
    is_animated = upload_emoji_image(image_file, emoji_file_name, author, content_type)

    realm_emoji.file_name = emoji_file_name
    realm_emoji.is_animated = is_animated
    realm_emoji.save(update_fields=["file_name", "is_animated"])

    realm_emoji_dict = get_all_custom_emoji_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=author,
        event_type=AuditLogEventType.REALM_EMOJI_ADDED,
        event_time=timezone_now(),
        extra_data={
            "realm_emoji": dict(sorted(realm_emoji_dict.items())),
            "added_emoji": realm_emoji_dict[str(realm_emoji.id)],
        },
    )
    notify_realm_emoji(realm_emoji.realm, realm_emoji_dict)
    return realm_emoji


@transaction.atomic(durable=True)
def do_remove_realm_emoji(realm: Realm, name: str, *, acting_user: UserProfile | None) -> None:
    emoji = RealmEmoji.objects.get(realm=realm, name=name, deactivated=False)
    emoji.deactivated = True
    emoji.save(update_fields=["deactivated"])

    realm_emoji_dict = get_all_custom_emoji_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.REALM_EMOJI_REMOVED,
        event_time=timezone_now(),
        extra_data={
            "realm_emoji": dict(sorted(realm_emoji_dict.items())),
            "deactivated_emoji": realm_emoji_dict[str(emoji.id)],
        },
    )

    notify_realm_emoji(realm, realm_emoji_dict)
