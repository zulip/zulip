from django.conf import settings

from zerver.models import Realm


def get_effective_jitsi_server_url(realm: Realm) -> str | None:
    if realm.jitsi_server_url is not None:
        return realm.jitsi_server_url.rstrip("/")
    if settings.JITSI_SERVER_URL is None:
        return None
    return settings.JITSI_SERVER_URL.rstrip("/")


def get_jitsi_jwt_config(jitsi_server_url: str | None) -> tuple[str, str, str] | None:
    if (
        jitsi_server_url is None
        or jitsi_server_url == "https://meet.jit.si"
        or settings.JITSI_SERVER_APP_ID is None
        or settings.JITSI_SERVER_APP_SECRET is None
    ):
        return None
    return (
        jitsi_server_url,
        settings.JITSI_SERVER_APP_ID,
        settings.JITSI_SERVER_APP_SECRET,
    )
