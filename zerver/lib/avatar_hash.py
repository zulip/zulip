from __future__ import absolute_import

from django.conf import settings
from typing import Text

from zerver.lib.utils import make_safe_digest

import hashlib

def gravatar_hash(email):
    # type: (Text) -> Text
    """Compute the Gravatar hash for an email address."""
    # Non-ASCII characters aren't permitted by the currently active e-mail
    # RFCs. However, the IETF has published https://tools.ietf.org/html/rfc4952,
    # outlining internationalization of email addresses, and regardless if we
    # typo an address or someone manages to give us a non-ASCII address, let's
    # not error out on it.
    return make_safe_digest(email.lower(), hashlib.md5)

def user_avatar_hash(email):
    # type: (Text) -> Text
    # Salting the user_key may be overkill, but it prevents us from
    # basically mimicking Gravatar's hashing scheme, which could lead
    # to some abuse scenarios like folks using us as a free Gravatar
    # replacement.
    user_key = email.lower() + settings.AVATAR_SALT
    return make_safe_digest(user_key, hashlib.sha1)

