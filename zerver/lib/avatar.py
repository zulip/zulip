from __future__ import absolute_import
from django.conf import settings

import hashlib
from zerver.lib.utils import make_safe_digest
if False:
    from zerver.models import UserProfile

from six import text_type

def gravatar_hash(email):
    # type: (text_type) -> text_type
    """Compute the Gravatar hash for an email address."""
    # Non-ASCII characters aren't permitted by the currently active e-mail
    # RFCs. However, the IETF has published https://tools.ietf.org/html/rfc4952,
    # outlining internationalization of email addresses, and regardless if we
    # typo an address or someone manages to give us a non-ASCII address, let's
    # not error out on it.
    return make_safe_digest(email.lower(), hashlib.md5)

def user_avatar_hash(email):
    # type: (text_type) -> text_type
    # Salting the user_key may be overkill, but it prevents us from
    # basically mimicking Gravatar's hashing scheme, which could lead
    # to some abuse scenarios like folks using us as a free Gravatar
    # replacement.
    user_key = email.lower() + settings.AVATAR_SALT
    return make_safe_digest(user_key, hashlib.sha1)

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
