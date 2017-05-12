from __future__ import absolute_import

from django.conf import settings
from typing import Text

from zerver.lib.utils import make_safe_digest

if False:
    # Typing import inside `if False` to avoid import loop.
    from zerver.models import UserProfile

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

# WARNING: If this method is changed, you may need to do a
# corresponding update to zerver/migrations/0060_move_avatars_to_be_uid_based.py
def user_avatar_hash(uid):
    # type: (Text) -> Text
    # Salting the user_key may be overkill, but it prevents us from
    # basically mimicking Gravatar's hashing scheme, which could lead
    # to some abuse scenarios like folks using us as a free Gravatar
    # replacement.
    user_key = uid + settings.AVATAR_SALT
    return make_safe_digest(user_key, hashlib.sha1)

# WARNING: If this method is changed, you will may to do a
# corresponding update to zerver/migrations/0060_move_avatars_to_be_uid_based.py
def user_avatar_path(user_profile):
    # type: (UserProfile) -> Text
    return user_avatar_path_from_ids(user_profile.id, user_profile.realm_id)

def user_avatar_path_from_ids(user_profile_id, realm_id):
    # type: (int, int) -> Text
    user_id_hash = user_avatar_hash(str(user_profile_id))
    return '%s/%s' % (str(realm_id), user_id_hash)
