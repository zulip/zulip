import urllib.parse
from typing import Any, Literal
from urllib.parse import urlsplit

import re2

from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.types import UserDisplayRecipient
from zerver.models import Realm, Stream, UserProfile

hash_replacements = {
    "%": ".",
    "(": ".28",
    ")": ".29",
    ".": ".2E",
}


def encode_hash_component(s: str) -> str:
    encoded = urllib.parse.quote(s, safe="*")
    return "".join(hash_replacements.get(c, c) for c in encoded)


def encode_stream(stream_id: int, stream_name: str, with_operator: bool = False) -> str:
    """
    This encodes the given `stream_id` and `stream_name`
    into a recipient slug string that can be used to
    construct a narrow URL.

    e.g., 9, "Verona" -> "99-Verona"

    The `with_operator` parameter decides whether to append
    the "channel" operator to the recipient slug or not.

    e.g., "channel/99-Verona"
    """
    # We encode stream for urls as something like .
    stream_name = stream_name.replace(" ", "-")
    encoded_stream = str(stream_id) + "-" + encode_hash_component(stream_name)
    if with_operator:
        return f"channel/{encoded_stream}"
    return encoded_stream


def encode_user_ids(
    user_ids: list[int],
    prefix: Literal["group", "pm"] = "group",
    with_operator: bool = False,
) -> str:
    """
    This encodes the given `user_ids` into recipient slug
    string that can be used to construct a narrow URL.

    e.g., [13, 23, 9] -> "13,23,9-group"

    The `with_operator` parameter decides whether to append
    the "dm" operator to the recipient slug or not.

    e.g., "dm/13,23,9-group"

    The `prefix` parameter is used to determine which format
    to use for the recipient slug.
     - "-pm" prefix is the "perma-link" format, the `user_ids`
        should include all users in the group direct message.
     - "-group" prefix is used  to format group links that only
        include the user ids of participants other than the
        client user.
    """
    assert len(user_ids) > 0
    pm_slug = ",".join([str(user_id) for user_id in sorted(user_ids)]) + "-" + prefix
    if with_operator:
        return f"dm/{pm_slug}"
    return pm_slug


def encode_full_name_and_id(full_name: str, user_id: int, with_operator: bool = False) -> str:
    """
    This encodes the given `full_name` and `user_id` into a
    recipient slug string that can be used to construct a
    narrow URL.

    e.g., 9, "King Hamlet" -> "9-King-Hamlet"

    The `with_operator` parameter decides whether to append
    the "dm" operator to the recipient slug or not.

    e.g., "dm/9-King-Hamlet"
    """
    encoded_user_name = re2.sub(r'[ "%\/<>`\p{C}]+', "-", full_name.strip())
    pm_slug = str(user_id) + "-" + encoded_user_name
    if with_operator:
        return f"dm/{pm_slug}"
    return pm_slug


def personal_narrow_url(*, realm: Realm, sender: UserProfile) -> str:
    base_url = f"{realm.url}/#narrow/dm/"
    pm_slug = encode_full_name_and_id(sender.full_name, sender.id)
    return base_url + pm_slug


def direct_message_group_narrow_url(
    *, user: UserProfile, display_recipient: list[UserDisplayRecipient]
) -> str:
    realm = user.realm
    other_user_ids = [r["id"] for r in display_recipient if r["id"] != user.id]
    pm_slug = encode_user_ids(other_user_ids, "group")
    base_url = f"{realm.url}/#narrow/dm/"
    return base_url + pm_slug


def stream_narrow_url(realm: Realm, stream: Stream) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return base_url + encode_stream(stream.id, stream.name)


def topic_narrow_url(*, realm: Realm, stream: Stream, topic_name: str) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return f"{base_url}{encode_stream(stream.id, stream.name)}/topic/{encode_hash_component(topic_name)}"


def near_message_url(realm: Realm, message: dict[str, Any]) -> str:
    if message["type"] == "stream":
        url = near_stream_message_url(
            realm=realm,
            message=message,
        )
        return url

    url = near_pm_message_url(
        realm=realm,
        message=message,
    )
    return url


def near_stream_message_url(realm: Realm, message: dict[str, Any]) -> str:
    message_id = str(message["id"])
    stream_id = message["stream_id"]
    stream_name = message["display_recipient"]
    topic_name = get_topic_from_message_info(message)
    encoded_topic_name = encode_hash_component(topic_name)
    encoded_stream = encode_stream(stream_id=stream_id, stream_name=stream_name)

    parts = [
        realm.url,
        "#narrow",
        "channel",
        encoded_stream,
        "topic",
        encoded_topic_name,
        "near",
        message_id,
    ]
    full_url = "/".join(parts)
    return full_url


def near_pm_message_url(realm: Realm, message: dict[str, Any]) -> str:
    message_id = str(message["id"])
    user_ids = [recipient["id"] for recipient in message["display_recipient"]]

    # Use the "perma-link" format here that includes the sender's
    # user_id, so they're easier to share between people.
    pm_str = encode_user_ids(user_ids, "pm")

    parts = [
        realm.url,
        "#narrow",
        "dm",
        pm_str,
        "near",
        message_id,
    ]
    full_url = "/".join(parts)
    return full_url


def append_url_query_string(original_url: str, query: str) -> str:
    u = urlsplit(original_url)
    query = u.query + ("&" if u.query and query else "") + query
    return u._replace(query=query).geturl()
