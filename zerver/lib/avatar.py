from urllib.parse import urljoin

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from zerver.lib.avatar_hash import (
    gravatar_hash,
    user_avatar_base_path_from_ids,
    user_avatar_content_hash,
)
from zerver.lib.thumbnail import MEDIUM_AVATAR_SIZE
from zerver.lib.upload import get_avatar_url
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import UserProfile
from zerver.models.users import is_cross_realm_bot_email
from django.urls import reverse
import hashlib
import subprocess
import hashlib
import os

STATIC_AVATARS_DIR = "images/static_avatars/"

DEFAULT_AVATAR_FILE = "images/default-avatar.png"


def avatar_url(
    user_profile: UserProfile, medium: bool = False, client_gravatar: bool = False
) -> str | None:
    # Fast-path: when the cached Realm object is available on the
    # UserProfile (the common case), use it to resolve realm-level
    # default avatar choices without hitting the database. This keeps
    # avatar URL generation O(1) in hot code paths.
    if user_profile.avatar_source == UserProfile.AVATAR_FROM_DEFAULT:
        realm = getattr(user_profile, "realm", None)
        if realm is not None:
            default_choice = getattr(realm, "default_newUser_avatar", None)
            if default_choice == "jdenticon":
                seed = hashlib.sha1((user_profile.delivery_email or str(user_profile.id)).encode()).hexdigest()
                size = 128 if medium else 80
                return reverse("jdenticon_svg", args=[seed, size])
            elif default_choice == "colorful_silhouette":
                seed = hashlib.sha1((user_profile.delivery_email or str(user_profile.id)).encode()).hexdigest()
                size = 128 if medium else 80
                return reverse("silhouette_svg", args=[seed, size])
            # If the realm default is gravatar or unknown, fall through and
            # let the existing logic handle gravatar/default-avatar cases.

    return get_avatar_field(
        user_id=user_profile.id,
        realm_id=user_profile.realm_id,
        email=user_profile.delivery_email,
        avatar_source=user_profile.avatar_source,
        avatar_version=user_profile.avatar_version,
        medium=medium,
        client_gravatar=client_gravatar,
    )


def get_system_bots_avatar_file_name(email: str) -> str:
    system_bot_avatar_name_map = {
        settings.WELCOME_BOT: "welcome-bot",
        settings.NOTIFICATION_BOT: "notification-bot",
        settings.EMAIL_GATEWAY_BOT: "emailgateway",
    }
    return urljoin(STATIC_AVATARS_DIR, system_bot_avatar_name_map.get(email, "unknown"))


def get_static_avatar_url(email: str, medium: bool) -> str:
    avatar_file_name = get_system_bots_avatar_file_name(email)
    avatar_file_name += "-medium.png" if medium else ".png"

    if settings.DEBUG:
        # This find call may not be cheap, so we only do it in the
        # development environment to do an assertion.
        from django.contrib.staticfiles.finders import find

        if not find(avatar_file_name):
            raise AssertionError(f"Unknown avatar file for: {email}")
    elif settings.STATIC_ROOT and not staticfiles_storage.exists(avatar_file_name):
        # Fallback for the case where no avatar exists; this should
        # never happen in practice. This logic cannot be executed
        # while STATIC_ROOT is not defined, so the above STATIC_ROOT
        # check is important.
        return DEFAULT_AVATAR_FILE

    return staticfiles_storage.url(avatar_file_name)

NODE = "node"
SCRIPT_PATH = os.path.join("tools", "jdenticon_generate.js")
def generate_jdenticon_svg(seed: str, size:int) -> str:
    result = subprocess.run(
        [NODE, SCRIPT_PATH, seed, str(size)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
    )
    return result.stdout


def get_avatar_field(
    user_id: int,
    realm_id: int,
    email: str,
    avatar_source: str,
    avatar_version: int,
    medium: bool,
    client_gravatar: bool,
) -> str | None:
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
    

    if avatar_source == UserProfile.AVATAR_FROM_DEFAULT:
        if realm_id is None:
            return staticfiles_storage.url("images/default-avatar.png")
        # We avoid any Realm DB lookups here. The higher-level `avatar_url`
        # function handles realm-based defaults using the cached
        # `UserProfile.realm` when available. When this lower-level API is
        # invoked without a UserProfile, fall back to gravatar/default.
        # Fall through to gravatar handling below.



    # System bots have hardcoded avatars
    if is_cross_realm_bot_email(email):
        return get_static_avatar_url(email, medium)

    """
    If our client knows how to calculate gravatar hashes, we
    will return None and let the client compute the gravatar
    url.
    """
    if (
        client_gravatar
        and settings.ENABLE_GRAVATAR
        and avatar_source == UserProfile.AVATAR_FROM_GRAVATAR
    ):
        return None

    """
    If we get this far, we'll compute an avatar URL that may be
    either user-uploaded or a gravatar, and then we'll add version
    info to try to avoid stale caches.
    """
    if avatar_source == "U":
        hash_key = user_avatar_base_path_from_ids(user_id, avatar_version, realm_id)
        return get_avatar_url(hash_key, medium=medium)

    return get_gravatar_url(
        email=email,
        avatar_version=avatar_version,
        realm_id=realm_id,
        medium=medium,
    )



def get_gravatar_url(email: str, avatar_version: int, realm_id: int, medium: bool = False) -> str:
    url = _get_unversioned_gravatar_url(email, medium, realm_id)
    return append_url_query_string(url, f"version={avatar_version:d}")


def _get_unversioned_gravatar_url(email: str, medium: bool, realm_id: int) -> str:
    use_gravatar = settings.ENABLE_GRAVATAR
    if realm_id in settings.GRAVATAR_REALM_OVERRIDE:
        use_gravatar = settings.GRAVATAR_REALM_OVERRIDE[realm_id]

    if use_gravatar:
        gravitar_query_suffix = f"&s={MEDIUM_AVATAR_SIZE}" if medium else ""
        hash_key = gravatar_hash(email)
        return f"https://secure.gravatar.com/avatar/{hash_key}?d=identicon{gravitar_query_suffix}"
    elif settings.DEFAULT_AVATAR_URI is not None:
        return settings.DEFAULT_AVATAR_URI
    else:
        return staticfiles_storage.url("images/default-avatar.png")


def absolute_avatar_url(user_profile: UserProfile) -> str:
    """
    Absolute URLs are used to simplify logic for applications that
    won't be served by browsers, such as rendering GCM notifications.
    """
    avatar = avatar_url(user_profile)
    # avatar_url can return None if client_gravatar=True, however here we use the default value of False
    assert avatar is not None
    return urljoin(user_profile.realm.url, avatar)


def is_avatar_new(ldap_avatar: bytes, user_profile: UserProfile) -> bool:
    new_avatar_hash = user_avatar_content_hash(ldap_avatar)

    if user_profile.avatar_hash and user_profile.avatar_hash == new_avatar_hash:
        # If an avatar exists and is the same as the new avatar,
        # then, no need to change the avatar.
        return False

    return True


def get_avatar_for_inaccessible_user() -> str:
    return staticfiles_storage.url("images/unknown-user-avatar.png")
