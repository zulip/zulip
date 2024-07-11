from typing import Optional

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.realm_background import realm_background_url
from zerver.models import Realm, RealmAuditLog, UserProfile
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_change_background_source(
    realm: Realm, background_source: str, *, acting_user: Optional[UserProfile]
) -> None:
    realm.background_source = background_source
    realm.background_version += 1
    realm.save(update_fields=["background_source", "background_version"])

    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_BACKGROUND_SOURCE_CHANGED,
        extra_data={
            "background_source": background_source,
            "background_version": realm.background_version,
        },
        event_time=event_time,
        acting_user=acting_user,
    )

    event = dict(
        type="realm",
        op="update_dict",
        property="background",
        data=dict(
            background_source=realm.background_source, background_url=realm_background_url(realm)
        ),
    )
    send_event_on_commit(
        realm,
        event,
        active_user_ids(realm.id),
    )
