import urllib
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from zerver.lib.avatar_hash import (
    gravatar_hash,
    user_avatar_content_hash,
    user_avatar_path_from_ids,
)
from zerver.lib.upload import get_avatar_url
from zerver.lib.upload.base import MEDIUM_AVATAR_SIZE
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import UserProfile


def avatar_url(
    user_profile: UserProfile, medium: bool = False, client_gravatar: bool = False
) -> Optional[str]:
    return get_avatar_field(
        user_id=user_profile.id,
        realm_id=user_profile.realm_id,
        email=user_profile.delivery_email,
        avatar_source=user_profile.avatar_source,
        avatar_version=user_profile.avatar_version,
        medium=medium,
        client_gravatar=client_gravatar,
    )


def avatar_url_from_dict(userdict: Dict[str, Any], medium: bool = False) -> str:
    """
    DEPRECATED: We should start using
                get_avatar_field to populate users,
                particularly for codepaths where the
                client can compute gravatar URLs
                on the client side.
    """
    url = _get_unversioned_avatar_url(
        userdict["id"],
        userdict["avatar_source"],
        userdict["realm_id"],
        email=userdict["email"],
        medium=medium,
    )
    return append_url_query_string(url, "version={:d}".format(userdict["avatar_version"]))


def get_avatar_field(
    user_id: int,
    realm_id: int,
    email: str,
    avatar_source: str,
    avatar_version: int,
    medium: bool,
    client_gravatar: bool,
) -> Optional[str]:
    """
    Most of the parameters to this function map to fields
    by the same name in UserProfile (avatar_source, realm_id,
    email, etc.).

    Then there are these:

        medium - This means we want a medium-sized avatar. This can
            affect the "s" parameter for gravatar avatars, or it
            can give us something like foo-medium.png for
            user-uploaded avatars.

        client_gravatar - If the client can compute their own
            gravatars, this will be set to True, and we'll avoid
            computing them on the server (mostly to save bandwidth).
    """

    if client_gravatar:
        """
        If our client knows how to calculate gravatar hashes, we
        will return None and let the client compute the gravatar
        url.
        """
        if settings.ENABLE_GRAVATAR and avatar_source == UserProfile.AVATAR_FROM_GRAVATAR:
            return None

    """
    If we get this far, we'll compute an avatar URL that may be
    either user-uploaded or a gravatar, and then we'll add version
    info to try to avoid stale caches.
    """
    url = _get_unversioned_avatar_url(
        user_profile_id=user_id,
        avatar_source=avatar_source,
        realm_id=realm_id,
        email=email,
        medium=medium,
    )
    return append_url_query_string(url, f"version={avatar_version:d}")


def get_gravatar_url(email: str, avatar_version: int, medium: bool = False) -> str:
    url = _get_unversioned_gravatar_url(email, medium)
    return append_url_query_string(url, f"version={avatar_version:d}")


def _get_unversioned_gravatar_url(email: str, medium: bool) -> str:
    if settings.ENABLE_GRAVATAR:
        gravitar_query_suffix = f"&s={MEDIUM_AVATAR_SIZE}" if medium else ""
        hash_key = gravatar_hash(email)
        return f"https://secure.gravatar.com/avatar/{hash_key}?d=identicon{gravitar_query_suffix}"
    elif settings.DEFAULT_AVATAR_URI is not None:
        return settings.DEFAULT_AVATAR_URI
    else:
        return staticfiles_storage.url("images/default-avatar.png")


def _get_unversioned_avatar_url(
    user_profile_id: int,
    avatar_source: str,
    realm_id: int,
    email: Optional[str] = None,
    medium: bool = False,
) -> str:
    if avatar_source == "U":
        hash_key = user_avatar_path_from_ids(user_profile_id, realm_id)
        return get_avatar_url(hash_key, medium=medium)
    assert email is not None
    return _get_unversioned_gravatar_url(email, medium)


def absolute_avatar_url(user_profile: UserProfile) -> str:
    """
    Absolute URLs are used to simplify logic for applications that
    won't be served by browsers, such as rendering GCM notifications.
    """
    avatar = avatar_url(user_profile)
    # avatar_url can return None if client_gravatar=True, however here we use the default value of False
    assert avatar is not None
    return urllib.parse.urljoin(user_profile.realm.uri, avatar)


def is_avatar_new(ldap_avatar: bytes, user_profile: UserProfile) -> bool:
    new_avatar_hash = user_avatar_content_hash(ldap_avatar)

    if user_profile.avatar_hash and user_profile.avatar_hash == new_avatar_hash:
        # If an avatar exists and is the same as the new avatar,
        # then, no need to change the avatar.
        return False

    return True
