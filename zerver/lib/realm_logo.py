from typing import Any, Dict

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from zerver.lib.upload import upload_backend
from zerver.models import Realm


def get_realm_logo_source(realm: Realm, night: bool) -> str:
    if realm.plan_type == Realm.PLAN_TYPE_LIMITED:
        return Realm.LOGO_DEFAULT
    if night:
        return realm.night_logo_source
    return realm.logo_source


def get_realm_logo_url(realm: Realm, night: bool) -> str:
    logo_source = get_realm_logo_source(realm, night)

    if logo_source == Realm.LOGO_UPLOADED:
        if night:
            logo_version = realm.night_logo_version
        else:
            logo_version = realm.logo_version
        return upload_backend.get_realm_logo_url(realm.id, logo_version, night)
    if settings.DEFAULT_LOGO_URI is not None:
        return settings.DEFAULT_LOGO_URI
    return staticfiles_storage.url("images/logo/zulip-org-logo.svg") + "?version=0"


def get_realm_logo_data(realm: Realm, night: bool) -> Dict[str, Any]:
    if night:
        return dict(
            night_logo_url=get_realm_logo_url(realm, night),
            night_logo_source=realm.night_logo_source,
        )
    return dict(logo_url=get_realm_logo_url(realm, night), logo_source=realm.logo_source)
