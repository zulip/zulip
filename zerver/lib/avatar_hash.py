import hashlib

from django.conf import settings

from zerver.lib.utils import make_safe_digest
from zerver.models import UserProfile


def gravatar_hash(email: str) -> str:
    """Compute the Gravatar hash for an email address."""
    # Non-ASCII characters aren't permitted by the currently active e-mail
    # RFCs. However, the IETF has published https://tools.ietf.org/html/rfc4952,
    # outlining internationalization of email addresses, and regardless if we
    # typo an address or someone manages to give us a non-ASCII address, let's
    # not error out on it.
    return make_safe_digest(email.lower(), hashlib.md5)


def user_avatar_hash(uid: str) -> str:
    # WARNING: If this method is changed, you may need to do a migration
    # similar to zerver/migrations/0060_move_avatars_to_be_uid_based.py .

    # The salt probably doesn't serve any purpose now.  In the past we
    # used a hash of the email address, not the user ID, and we salted
    # it in order to make the hashing scheme different from Gravatar's.
    user_key = uid + settings.AVATAR_SALT
    return make_safe_digest(user_key, hashlib.sha1)


def user_avatar_path(user_profile: UserProfile) -> str:
    # WARNING: If this method is changed, you may need to do a migration
    # similar to zerver/migrations/0060_move_avatars_to_be_uid_based.py .
    return user_avatar_path_from_ids(user_profile.id, user_profile.realm_id)


def user_avatar_path_from_ids(user_profile_id: int, realm_id: int) -> str:
    user_id_hash = user_avatar_hash(str(user_profile_id))
    return f"{str(realm_id)}/{user_id_hash}"


def user_avatar_content_hash(ldap_avatar: bytes) -> str:
    return hashlib.sha256(ldap_avatar).hexdigest()
