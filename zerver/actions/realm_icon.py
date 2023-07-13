from typing import Optional

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.realm_icon import realm_icon_url
from zerver.models import Realm, RealmAuditLog, UserProfile, active_user_ids
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_change_icon_source(
    realm: Realm, icon_source: str, *, acting_user: Optional[UserProfile]
) -> None:
    realm.icon_source = icon_source
    realm.icon_version += 1
    realm.save(update_fields=["icon_source", "icon_version"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_ICON_SOURCE_CHANGED,
        extra_data={"icon_source": icon_source, "icon_version": realm.icon_version},
        event_time=event_time,
        acting_user=acting_user,
    )

    event = dict(
        type="realm",
        op="update_dict",
        property="icon",
        data=dict(icon_source=realm.icon_source, icon_url=realm_icon_url(realm)),
    )
    send_event_on_commit(
        realm,
        event,
        active_user_ids(realm.id),
    )
