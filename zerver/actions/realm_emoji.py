from typing import IO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.emoji import get_emoji_file_name
from zerver.lib.exceptions import JsonableError
from zerver.lib.mime_types import INLINE_MIME_TYPES, bare_content_type
from zerver.lib.thumbnail import THUMBNAIL_ACCEPT_IMAGE_TYPES, BadImageError
from zerver.lib.upload import upload_emoji_image
from zerver.models import Realm, RealmAuditLog, RealmEmoji, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realm_emoji import emoji_as_emojiinfo
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def check_add_realm_emoji(
    realm: Realm, name: str, author: UserProfile, image_file: IO[bytes], content_type: str
) -> RealmEmoji:
    content_type = bare_content_type(content_type)
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

    new_emoji = emoji_as_emojiinfo(realm_emoji)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=author,
        event_type=AuditLogEventType.REALM_EMOJI_ADDED,
        event_time=timezone_now(),
        extra_data={
            "added_emoji": new_emoji,
        },
    )
    event = dict(type="realm_emoji", op="add", emoji=new_emoji)
    send_event_on_commit(realm, event, active_user_ids(realm.id))
    return realm_emoji


@transaction.atomic(durable=True)
def do_remove_realm_emoji(realm: Realm, name: str, *, acting_user: UserProfile | None) -> None:
    realm_emoji = RealmEmoji.objects.get(realm=realm, name=name, deactivated=False)
    realm_emoji.deactivated = True
    realm_emoji.save(update_fields=["deactivated"])

    removed_emoji = emoji_as_emojiinfo(realm_emoji)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=AuditLogEventType.REALM_EMOJI_REMOVED,
        event_time=timezone_now(),
        extra_data={
            "deactivated_emoji": removed_emoji,
        },
    )

    event = dict(type="realm_emoji", op="remove", emoji=removed_emoji)
    send_event_on_commit(realm, event, active_user_ids(realm.id))
