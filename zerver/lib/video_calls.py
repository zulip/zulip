from django.conf import settings

from zerver.models import Realm


def get_effective_jitsi_server_url(realm: Realm) -> str | None:
    if realm.jitsi_server_url is not None:
        return realm.jitsi_server_url.rstrip("/")
    if settings.JITSI_SERVER_URL is None:
        return None
    return settings.JITSI_SERVER_URL.rstrip("/")


def server_jitsi_jwt_configured() -> bool:
    return (
        settings.JITSI_SERVER_URL is not None
        and settings.JITSI_SERVER_URL != "https://meet.jit.si"
        and settings.JITSI_SERVER_APP_ID is not None
        and settings.JITSI_SERVER_APP_SECRET is not None
    )


def get_jitsi_jwt_config(realm: Realm) -> tuple[str, str, str] | None:
    # The server's JWT credentials are for settings.JITSI_SERVER_URL; a
    # realm that overrides the URL points at a Jitsi server that does
    # not know that secret, so we must not sign tokens for it.
    if realm.jitsi_server_url is not None:
        return None
    if not server_jitsi_jwt_configured():
        return None
    assert settings.JITSI_SERVER_URL is not None
    assert settings.JITSI_SERVER_APP_ID is not None
    assert settings.JITSI_SERVER_APP_SECRET is not None
    return (
        settings.JITSI_SERVER_URL.rstrip("/"),
        settings.JITSI_SERVER_APP_ID,
        settings.JITSI_SERVER_APP_SECRET,
    )
