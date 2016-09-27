from __future__ import absolute_import
from django.conf import settings

if False:
    from zerver.models import UserProfile

from six import text_type

from zerver.lib.avatar_hash import gravatar_hash, user_avatar_hash

def avatar_url(user_profile):
    # type: (UserProfile) -> text_type
    return get_avatar_url(
            user_profile.avatar_source,
            user_profile.email
    )

def get_avatar_url(avatar_source, email):
    # type: (text_type, text_type) -> text_type
    if avatar_source == u'U':
        hash_key = user_avatar_hash(email)
        if settings.LOCAL_UPLOADS_DIR is not None:
            # ?x=x allows templates to append additional parameters with &s
            return u"/user_avatars/%s.png?x=x" % (hash_key)
        else:
            bucket = settings.S3_AVATAR_BUCKET
            return u"https://%s.s3.amazonaws.com/%s?x=x" % (bucket, hash_key)
    elif settings.ENABLE_GRAVATAR:
        hash_key = gravatar_hash(email)
        return u"https://secure.gravatar.com/avatar/%s?d=identicon" % (hash_key,)
    else:
        return settings.DEFAULT_AVATAR_URI+'?x=x'
