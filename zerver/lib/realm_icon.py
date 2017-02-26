from __future__ import absolute_import
from django.conf import settings

if False:
    from zerver.models import Realm

from typing import Text

from zerver.lib.avatar_hash import gravatar_hash, user_avatar_hash
from zerver.lib.upload import upload_backend

def realm_icon_url(realm):
    # type: (Realm) -> Text
    return get_realm_icon_url(realm)


def get_realm_icon_url(realm):
    # type: (Realm) -> Text
    if realm.icon_source == u'U':
        return upload_backend.get_realm_icon_url(realm.id, realm.icon_version)
    elif settings.ENABLE_GRAVATAR:
        hash_key = gravatar_hash(realm.domain)
        return u"https://secure.gravatar.com/avatar/%s?d=identicon" % (hash_key,)
    else:
        return settings.DEFAULT_AVATAR_URI+'?version=0'
