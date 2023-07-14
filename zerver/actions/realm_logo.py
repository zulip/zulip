from typing import Optional

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.realm_logo import get_realm_logo_data
from zerver.models import Realm, RealmAuditLog, UserProfile, active_user_ids
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_change_logo_source(
    realm: Realm, logo_source: str, night: bool, *, acting_user: Optional[UserProfile]
) -> None:
    if not night:
        realm.logo_source = logo_source
        realm.logo_version += 1
        realm.save(update_fields=["logo_source", "logo_version"])

    else:
        realm.night_logo_source = logo_source
        realm.night_logo_version += 1
        realm.save(update_fields=["night_logo_source", "night_logo_version"])

    RealmAuditLog.objects.create(
        event_type=RealmAuditLog.REALM_LOGO_CHANGED,
        realm=realm,
        event_time=timezone_now(),
        acting_user=acting_user,
    )

    event = dict(
        type="realm",
        op="update_dict",
        property="night_logo" if night else "logo",
        data=get_realm_logo_data(realm, night),
    )
    send_event_on_commit(realm, event, active_user_ids(realm.id))
