from django.conf import settings

from zerver.lib.avatar_hash import gravatar_hash
from zerver.lib.upload import upload_backend
from zerver.models import Realm

def realm_icon_url(realm: Realm) -> str:
    return get_realm_icon_url(realm)

def get_realm_icon_url(realm: Realm) -> str:
    if realm.icon_source == 'U':
        return upload_backend.get_realm_icon_url(realm.id, realm.icon_version)
    elif settings.ENABLE_GRAVATAR:
        hash_key = gravatar_hash(realm.string_id)
        return "https://secure.gravatar.com/avatar/%s?d=identicon" % (hash_key,)
    else:
        return settings.DEFAULT_AVATAR_URI+'?version=0'
