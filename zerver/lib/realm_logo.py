from django.conf import settings

from zerver.lib.upload import upload_backend
from zerver.models import Realm

def realm_logo_url(realm: Realm) -> str:
    return get_realm_logo_url(realm)

def get_realm_logo_url(realm: Realm) -> str:
    if realm.logo_source == 'U':
        return upload_backend.get_realm_logo_url(realm.id, realm.logo_version)
    else:
        return settings.DEFAULT_LOGO_URI+'?version=0'
