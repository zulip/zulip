from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from zerver.lib.upload import upload_backend
from zerver.models import Realm


def realm_background_url(realm: Realm) -> str:
    return get_realm_background_url(realm)


def get_realm_background_url(realm: Realm) -> str:
    if realm.background_source == "U":
        return upload_backend.get_realm_background_url(realm.id, realm.background_version)
    elif settings.DEFAULT_BACKGROUND_URI is not None:
        return settings.DEFAULT_BACKGROUND_URI
    else:
        return (
            staticfiles_storage.url("images/login-background/default-background.png") + "?version=0"
        )
