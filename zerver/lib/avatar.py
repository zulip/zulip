import logging
import os
import subprocess
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from zerver.lib.avatar_hash import (
    gravatar_hash,
    user_avatar_base_path_from_ids,
    user_avatar_content_hash,
    user_avatar_path,
)
from zerver.lib.thumbnail import DEFAULT_AVATAR_SIZE, MEDIUM_AVATAR_SIZE
from zerver.lib.upload import get_avatar_url, write_jdenticon_avatars
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import UserProfile
from zerver.models.users import is_cross_realm_bot_email

STATIC_AVATARS_DIR = "images/static_avatars/"

DEFAULT_AVATAR_FILE = "images/default-avatar.png"

logger = logging.getLogger(__name__)


def avatar_url(
    user_profile: UserProfile, medium: bool = False, client_gravatar: bool = False
) -> str | None:
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
    If we get this far, we'll compute an avatar URL based on the
    avatar source, and then we'll add version info to try to avoid
    stale caches.
    """
    if avatar_source in [UserProfile.AVATAR_FROM_USER, UserProfile.AVATAR_FROM_JDENTICON]:
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


def absolute_avatar_url(
    user_profile: UserProfile,
    # Pass `realm_url` to avoid a DB query when `user_profile.realm` isn't
    # already loaded but the caller has realm available from another source.
    realm_url: str | None = None,
) -> str:
    """
    Absolute URLs are used to simplify logic for applications that
    won't be served by browsers, such as rendering GCM notifications.
    """
    avatar = avatar_url(user_profile)
    # avatar_url can return None if client_gravatar=True, however here we use the default value of False
    assert avatar is not None
    if realm_url is None:
        realm_url = user_profile.realm.url
    return urljoin(realm_url, avatar)


def is_avatar_new(ldap_avatar: bytes, user_profile: UserProfile) -> bool:
    new_avatar_hash = user_avatar_content_hash(ldap_avatar)

    if user_profile.avatar_hash and user_profile.avatar_hash == new_avatar_hash:
        # If an avatar exists and is the same as the new avatar,
        # then, no need to change the avatar.
        return False

    return True


def get_avatar_for_inaccessible_user() -> str:
    return staticfiles_storage.url("images/unknown-user-avatar.png")


def generate_avatar_jdenticon(input: str, medium: bool) -> bytes:
    from zerver.lib.storage import static_path

    jdenticon_path = (
        static_path("webpack-bundles/jdenticon.js")
        if settings.PRODUCTION
        else os.path.join(settings.DEPLOY_ROOT, "node_modules/jdenticon/bin/jdenticon.js")
    )
    size = str(MEDIUM_AVATAR_SIZE if medium else DEFAULT_AVATAR_SIZE)
    command = [
        "node",
        jdenticon_path,
        input,
        "-s",
        size,
        "-p",
        "0",
        "--lightness-color",
        "0.3,0.7",
        "--lightness-grayscale",
        "0.3,0.7",
    ]
    try:
        stdout = subprocess.check_output(command)
        return stdout
    except subprocess.CalledProcessError as error:  # nocoverage
        logger.exception("Jdenticon generation failed for user_id:{input}")
        raise error


def generate_and_upload_jdenticon_avatar(
    user_profile: UserProfile,
    realm_uuid: str,
    future: bool,
) -> None:
    # We use a combination of user ID and realm_uuid (salt) as the key
    # for Jdenticon generation, so that clients that prefer to use computation
    # instead of network to provide default avatars for users can do that
    # in the future.
    #
    # Using only user ID (no salt) can result in situations where a person is
    # part of multiple zulip servers, and they find same avatar for different
    # people in different servers.
    #
    # Note: The key effectively changes when user IDs are renumbered when
    # migrating between Zulip servers,
    jdenticon_key = f"{realm_uuid}:{user_profile.id}"
    image_data = generate_avatar_jdenticon(jdenticon_key, medium=False)
    image_data_medium = generate_avatar_jdenticon(jdenticon_key, medium=True)
    file_path = user_avatar_path(user_profile, future)

    write_jdenticon_avatars(
        file_path,
        user_profile,
        image_data=image_data,
        image_data_medium=image_data_medium,
        future=future,
    )
