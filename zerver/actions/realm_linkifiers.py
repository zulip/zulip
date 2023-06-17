from typing import Dict, List, Optional

import orjson
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.types import LinkifierDict
from zerver.models import (
    Realm,
    RealmAuditLog,
    RealmFilter,
    UserProfile,
    active_user_ids,
    linkifiers_for_realm,
)
from zerver.tornado.django_api import send_event_on_commit


def notify_linkifiers(realm: Realm, realm_linkifiers: List[LinkifierDict]) -> None:
    event: Dict[str, object] = dict(type="realm_linkifiers", realm_linkifiers=realm_linkifiers)
    send_event_on_commit(realm, event, active_user_ids(realm.id))


# NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
# RegExp syntax. In addition to JS-compatible syntax, the following features are available:
#   * Named groups will be converted to numbered groups automatically
#   * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags
@transaction.atomic(durable=True)
def do_add_linkifier(
    realm: Realm,
    pattern: str,
    url_template: str,
    *,
    acting_user: Optional[UserProfile],
) -> int:
    pattern = pattern.strip()
    url_template = url_template.strip()
    linkifier = RealmFilter(realm=realm, pattern=pattern, url_template=url_template)
    linkifier.full_clean()
    linkifier.save()

    realm_linkifiers = linkifiers_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_LINKIFIER_ADDED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_linkifiers": realm_linkifiers,
                "added_linkifier": LinkifierDict(
                    pattern=pattern,
                    url_template=url_template,
                    id=linkifier.id,
                ),
            }
        ).decode(),
    )
    notify_linkifiers(realm, realm_linkifiers)

    return linkifier.id


@transaction.atomic(durable=True)
def do_remove_linkifier(
    realm: Realm,
    pattern: Optional[str] = None,
    id: Optional[int] = None,
    *,
    acting_user: Optional[UserProfile] = None,
) -> None:
    if pattern is not None:
        realm_linkifier = RealmFilter.objects.get(realm=realm, pattern=pattern)
    else:
        assert id is not None
        realm_linkifier = RealmFilter.objects.get(realm=realm, id=id)

    pattern = realm_linkifier.pattern
    url_template = realm_linkifier.url_template
    realm_linkifier.delete()

    realm_linkifiers = linkifiers_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_LINKIFIER_REMOVED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_linkifiers": realm_linkifiers,
                "removed_linkifier": {"pattern": pattern, "url_template": url_template},
            }
        ).decode(),
    )
    notify_linkifiers(realm, realm_linkifiers)


@transaction.atomic(durable=True)
def do_update_linkifier(
    realm: Realm,
    id: int,
    pattern: str,
    url_template: str,
    *,
    acting_user: Optional[UserProfile],
) -> None:
    pattern = pattern.strip()
    url_template = url_template.strip()
    linkifier = RealmFilter.objects.get(realm=realm, id=id)
    linkifier.pattern = pattern
    linkifier.url_template = url_template
    linkifier.full_clean()
    linkifier.save(update_fields=["pattern", "url_template"])

    realm_linkifiers = linkifiers_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_LINKIFIER_CHANGED,
        event_time=timezone_now(),
        extra_data=orjson.dumps(
            {
                "realm_linkifiers": realm_linkifiers,
                "changed_linkifier": LinkifierDict(
                    pattern=pattern,
                    url_template=url_template,
                    id=linkifier.id,
                ),
            }
        ).decode(),
    )

    notify_linkifiers(realm, realm_linkifiers)
