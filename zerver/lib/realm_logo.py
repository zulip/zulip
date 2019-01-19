from django.conf import settings

from zerver.lib.upload import upload_backend
from zerver.models import Realm

def realm_logo_url(realm: Realm, night: bool) -> str:
    return get_realm_logo_url(realm, night)

def get_realm_logo_url(realm: Realm, night: bool) -> str:
    if not night:
        if realm.logo_source == 'U':
            return upload_backend.get_realm_logo_url(realm.id, realm.logo_version, night)
        else:
            return settings.DEFAULT_LOGO_URI+'?version=0'
    else:
        if realm.night_logo_source == 'U':
            return upload_backend.get_realm_logo_url(realm.id, realm.night_logo_version, night)
        else:
            return settings.DEFAULT_LOGO_URI+'?version=0'
