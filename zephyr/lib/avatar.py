from __future__ import absolute_import
from django.conf import settings

import hashlib
from zephyr.lib.utils import make_safe_digest

def gravatar_hash(email):
    """Compute the Gravatar hash for an email address."""
    # Non-ASCII characters aren't permitted by the currently active e-mail
    # RFCs. However, the IETF has published https://tools.ietf.org/html/rfc4952,
    # outlining internationalization of email addresses, and regardless if we
    # typo an address or someone manages to give us a non-ASCII address, let's
    # not error out on it.
    return make_safe_digest(email.lower(), hashlib.md5)

def user_avatar_hash(email):
    # Salting the user_key may be overkill, but it prevents us from
    # basically mimicking Gravatar's hashing scheme, which could lead
    # to some abuse scenarios like folks using us as a free Gravatar
    # replacement.
    user_key = email.lower() + settings.AVATAR_SALT
    return make_safe_digest(user_key, hashlib.sha1)

def avatar_url(user_profile):
    if user_profile.avatar_source == 'U':
        bucket = settings.S3_AVATAR_BUCKET
        hash_key = user_avatar_hash(user_profile.email)
        # ?x=x allows templates to append additional parameters with &s
        return "https://%s.s3.amazonaws.com/%s?x=x" % (bucket, hash_key)
    else:
        hash_key = gravatar_hash(user_profile.email)
        return "https://secure.gravatar.com/avatar/%s?d=identicon" % (hash_key,)
