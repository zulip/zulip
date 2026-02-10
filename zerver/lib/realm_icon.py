from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from zerver.lib.avatar_hash import gravatar_hash
from zerver.lib.upload import upload_backend
from zerver.models import Realm


def realm_icon_url(realm: Realm) -> str:
    return get_realm_icon_url(realm)


def get_realm_icon_url(realm: Realm) -> str:
    if realm.icon_source == "U":
        return upload_backend.get_realm_icon_url(realm.id, realm.icon_version)
    elif settings.ENABLE_GRAVATAR:
        hash_key = gravatar_hash(realm.string_id)
        return f"https://secure.gravatar.com/avatar/{hash_key}?d=identicon"
    elif settings.DEFAULT_AVATAR_URI is not None:
        return settings.DEFAULT_AVATAR_URI
    else:
        return staticfiles_storage.url("images/default-avatar.png") + "?version=0"
