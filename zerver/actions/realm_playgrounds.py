from typing import List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.exceptions import ValidationFailureError
from zerver.lib.types import RealmPlaygroundDict
from zerver.models import (
    Realm,
    RealmAuditLog,
    RealmPlayground,
    UserProfile,
    active_user_ids,
    get_realm_playgrounds,
)
from zerver.tornado.django_api import send_event_on_commit


def notify_realm_playgrounds(realm: Realm, realm_playgrounds: List[RealmPlaygroundDict]) -> None:
    event = dict(type="realm_playgrounds", realm_playgrounds=realm_playgrounds)
    send_event_on_commit(realm, event, active_user_ids(realm.id))


@transaction.atomic(durable=True)
def check_add_realm_playground(
    realm: Realm,
    *,
    acting_user: Optional[UserProfile],
    name: str,
    pygments_language: str,
    url_template: str,
) -> int:
    realm_playground = RealmPlayground(
        realm=realm,
        name=name,
        pygments_language=pygments_language,
        url_template=url_template,
    )
    # The additional validations using url_template_validaton
    # check_pygments_language, etc are included in full_clean.
    # Because we want to avoid raising ValidationError from this check_*
    # function, we do error handling here to turn it into a JsonableError.
    try:
        realm_playground.full_clean()
    except ValidationError as e:
        raise ValidationFailureError(e)
    realm_playground.save()
    realm_playgrounds = get_realm_playgrounds(realm)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_PLAYGROUND_ADDED,
        event_time=timezone_now(),
        extra_data={
            "realm_playgrounds": realm_playgrounds,
            "added_playground": RealmPlaygroundDict(
                id=realm_playground.id,
                name=realm_playground.name,
                pygments_language=realm_playground.pygments_language,
                url_template=realm_playground.url_template,
            ),
        },
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
        "url_template": realm_playground.url_template,
    }

    realm_playground.delete()
    realm_playgrounds = get_realm_playgrounds(realm)

    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_PLAYGROUND_REMOVED,
        event_time=timezone_now(),
        extra_data={
            "realm_playgrounds": realm_playgrounds,
            "removed_playground": removed_playground,
        },
    )

    notify_realm_playgrounds(realm, realm_playgrounds)
