from __future__ import absolute_import
from django.conf import settings

if False:
    from zerver.models import UserProfile

from typing import Text

from zerver.lib.avatar_hash import gravatar_hash, user_avatar_hash
from zerver.lib.upload import upload_backend, MEDIUM_AVATAR_SIZE

def avatar_url(user_profile, medium=False):
    # type: (UserProfile, bool) -> Text
    return get_avatar_url(
            user_profile.avatar_source,
            user_profile.email,
            medium=medium)

def get_avatar_url(avatar_source, email, medium=False):
    # type: (Text, Text, bool) -> Text
    if avatar_source == u'U':
        hash_key = user_avatar_hash(email)
        return upload_backend.get_avatar_url(hash_key, medium=medium)
    elif settings.ENABLE_GRAVATAR:
        gravitar_query_suffix = "&s=%s" % (MEDIUM_AVATAR_SIZE,) if medium else ""
        hash_key = gravatar_hash(email)
        return u"https://secure.gravatar.com/avatar/%s?d=identicon%s" % (hash_key, gravitar_query_suffix)
    else:
        return settings.DEFAULT_AVATAR_URI+'?x=x'
