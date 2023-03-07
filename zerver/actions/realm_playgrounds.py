from typing import Any, List, Optional

import orjson
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.types import RealmPlaygroundDict
from zerver.models import (
    Realm,
    RealmAuditLog,
    RealmPlayground,
    UserProfile,
    active_user_ids,
    get_realm_playgrounds,
)
from zerver.tornado.django_api import send_event


def notify_realm_playgrounds(realm: Realm, realm_playgrounds: List[RealmPlaygroundDict]) -> None:
    event = dict(type="realm_playgrounds", realm_playgrounds=realm_playgrounds)
    transaction.on_commit(lambda: send_event(realm, event, active_user_ids(realm.id)))


@transaction.atomic(durable=True)
def do_add_realm_playground(
    realm: Realm, *, acting_user: Optional[UserProfile], **kwargs: Any
) -> int:
    realm_playground = RealmPlayground(realm=realm, **kwargs)
    # We expect full_clean to always pass since a thorough input validation
    # is performed in the view (using check_url, check_pygments_language, etc)
    # before calling this function.
    realm_playground.full_clean()
    realm_playground.save()
    realm_playgrounds = get_realm_playgrounds(realm)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_PLAYGROUND_ADDED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_playgrounds": realm_playgrounds,
                "added_playground": RealmPlaygroundDict(
                    id=realm_playground.id,
                    name=realm_playground.name,
                    pygments_language=realm_playground.pygments_language,
                    url_prefix=realm_playground.url_prefix,
                ),
            }
        ).decode(),
    )
    notify_realm_playgrounds(realm, realm_playgrounds)
    return realm_playground.id


@transaction.atomic(durable=True)
def do_remove_realm_playground(
    realm: Realm, realm_playground: RealmPlayground, *, acting_user: Optional[UserProfile]
) -> None:
    removed_playground = {
        "name": realm_playground.name,
        "pygments_language": realm_playground.pygments_language,
        "url_prefix": realm_playground.url_prefix,
    }

    realm_playground.delete()
    realm_playgrounds = get_realm_playgrounds(realm)

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_PLAYGROUND_REMOVED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_playgrounds": realm_playgrounds,
                "removed_playground": removed_playground,
            }
        ).decode(),
    )

    notify_realm_playgrounds(realm, realm_playgrounds)
