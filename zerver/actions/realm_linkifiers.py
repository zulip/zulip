from typing import Dict, Optional

from zerver.models import (
    Realm,
    RealmFilter,
    active_user_ids,
    linkifiers_for_realm,
    realm_filters_for_realm,
)
from zerver.tornado.django_api import send_event


def notify_linkifiers(realm: Realm) -> None:
    realm_linkifiers = linkifiers_for_realm(realm.id)
    event: Dict[str, object] = dict(type="realm_linkifiers", realm_linkifiers=realm_linkifiers)
    send_event(realm, event, active_user_ids(realm.id))

    # Below is code for backwards compatibility. The now deprecated
    # "realm_filters" event-type is used by older clients, and uses
    # tuples.
    realm_filters = realm_filters_for_realm(realm.id)
    event = dict(type="realm_filters", realm_filters=realm_filters)
    send_event(realm, event, active_user_ids(realm.id))


# NOTE: Regexes must be simple enough that they can be easily translated to JavaScript
# RegExp syntax. In addition to JS-compatible syntax, the following features are available:
#   * Named groups will be converted to numbered groups automatically
#   * Inline-regex flags will be stripped, and where possible translated to RegExp-wide flags
def do_add_linkifier(realm: Realm, pattern: str, url_format_string: str) -> int:
    pattern = pattern.strip()
    url_format_string = url_format_string.strip()
    linkifier = RealmFilter(realm=realm, pattern=pattern, url_format_string=url_format_string)
    linkifier.full_clean()
    linkifier.save()
    notify_linkifiers(realm)

    return linkifier.id


def do_remove_linkifier(
    realm: Realm, pattern: Optional[str] = None, id: Optional[int] = None
) -> None:
    if pattern is not None:
        RealmFilter.objects.get(realm=realm, pattern=pattern).delete()
    else:
        RealmFilter.objects.get(realm=realm, id=id).delete()
    notify_linkifiers(realm)


def do_update_linkifier(realm: Realm, id: int, pattern: str, url_format_string: str) -> None:
    pattern = pattern.strip()
    url_format_string = url_format_string.strip()
    linkifier = RealmFilter.objects.get(realm=realm, id=id)
    linkifier.pattern = pattern
    linkifier.url_format_string = url_format_string
    linkifier.full_clean()
    linkifier.save(update_fields=["pattern", "url_format_string"])
    notify_linkifiers(realm)
