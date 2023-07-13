from typing import Dict, List, Optional

from django.db import transaction
from django.db.models import Max
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.types import LinkifierDict
from zerver.models import (
    Realm,
    RealmAuditLog,
    RealmFilter,
    UserProfile,
    active_user_ids,
    flush_linkifiers,
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
    # This makes sure that the new linkifier is always ordered the last modulo
    # the rare race condition.
    max_order = RealmFilter.objects.aggregate(Max("order"))["order__max"]
    if max_order is None:
        linkifier = RealmFilter(realm=realm, pattern=pattern, url_template=url_template)
    else:
        linkifier = RealmFilter(
            realm=realm, pattern=pattern, url_template=url_template, order=max_order + 1
        )
    linkifier.full_clean()
    linkifier.save()

    realm_linkifiers = linkifiers_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_LINKIFIER_ADDED,
        event_time=timezone_now(),
        extra_data={
            "realm_linkifiers": realm_linkifiers,
            "added_linkifier": LinkifierDict(
                pattern=pattern,
                url_template=url_template,
                id=linkifier.id,
            ),
        },
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
        extra_data={
            "realm_linkifiers": realm_linkifiers,
            "removed_linkifier": {
                "pattern": pattern,
                "url_template": url_template,
            },
        },
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
        extra_data={
            "realm_linkifiers": realm_linkifiers,
            "changed_linkifier": LinkifierDict(
                pattern=pattern,
                url_template=url_template,
                id=linkifier.id,
            ),
        },
    )

    notify_linkifiers(realm, realm_linkifiers)


@transaction.atomic(durable=True)
def check_reorder_linkifiers(
    realm: Realm, ordered_linkifier_ids: List[int], *, acting_user: Optional[UserProfile]
) -> None:
    """ordered_linkifier_ids should contain ids of all existing linkifiers.
    In the rare situation when any of the linkifier gets deleted that more ids
    are passed, the checks below are sufficient to detect inconsistencies most of
    the time."""
    # Repeated IDs in the user request would collapse into the same key when
    # constructing the set.
    linkifier_id_set = set(ordered_linkifier_ids)
    if len(linkifier_id_set) < len(ordered_linkifier_ids):
        raise JsonableError(_("The ordered list must not contain duplicated linkifiers"))

    linkifiers = RealmFilter.objects.filter(realm=realm)
    if {linkifier.id for linkifier in linkifiers} != linkifier_id_set:
        raise JsonableError(
            _("The ordered list must enumerate all existing linkifiers exactly once")
        )

    # After the validation, we are sure that there is nothing to do. Return
    # early to avoid flushing the cache and populating the audit logs.
    if len(linkifiers) == 0:
        return

    id_to_new_order = {
        linkifier_id: order for order, linkifier_id in enumerate(ordered_linkifier_ids)
    }

    for linkifier in linkifiers:
        assert linkifier.id in id_to_new_order
        linkifier.order = id_to_new_order[linkifier.id]
    RealmFilter.objects.bulk_update(linkifiers, fields=["order"])
    flush_linkifiers(instance=linkifiers[0])

    # This roundtrip re-fetches the linkifiers sorted in the new order.
    realm_linkifiers = linkifiers_for_realm(realm.id)
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_LINKIFIERS_REORDERED,
        event_time=timezone_now(),
        extra_data={
            "realm_linkifiers": realm_linkifiers,
        },
    )
    notify_linkifiers(realm, realm_linkifiers)
