from typing import IO

import django.db.utils
from django.utils.translation import gettext as _

from zerver.lib.emoji import get_emoji_file_name
from zerver.lib.exceptions import JsonableError
from zerver.lib.pysa import mark_sanitized
from zerver.lib.upload import upload_emoji_image
from zerver.models import Realm, RealmEmoji, UserProfile, active_user_ids
from zerver.tornado.django_api import send_event


def notify_realm_emoji(realm: Realm) -> None:
    event = dict(type="realm_emoji", op="update", realm_emoji=realm.get_emoji())
    send_event(realm, event, active_user_ids(realm.id))


def check_add_realm_emoji(
    realm: Realm, name: str, author: UserProfile, image_file: IO[bytes]
) -> RealmEmoji:
    try:
        realm_emoji = RealmEmoji(realm=realm, name=name, author=author)
        realm_emoji.full_clean()
        realm_emoji.save()
    except django.db.utils.IntegrityError:
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
    notify_realm_emoji(realm_emoji.realm)
    return realm_emoji


def do_remove_realm_emoji(realm: Realm, name: str) -> None:
    emoji = RealmEmoji.objects.get(realm=realm, name=name, deactivated=False)
    emoji.deactivated = True
    emoji.save(update_fields=["deactivated"])
    notify_realm_emoji(realm)
