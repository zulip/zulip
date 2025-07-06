import urllib.parse
from typing import Any
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


def encode_channel(channel_id: int, channel_name: str, with_operator: bool = False) -> str:
    """
    This encodes the given `channel_id` and `channel_name`
    into a recipient slug string that can be used to
    construct a narrow URL.

    e.g., 9, "Verona" -> "99-Verona"

    The `with_operator` parameter decides whether to append
    the "channel" operator to the recipient slug or not.

    e.g., "channel/99-Verona"
    """
    channel_name = channel_name.replace(" ", "-")
    encoded_channel = str(channel_id) + "-" + encode_hash_component(channel_name)
    if with_operator:
        return f"channel/{encoded_channel}"
    return encoded_channel


def encode_user_ids(
    user_ids: list[int],
    with_operator: bool = False,
) -> str:
    """
    This encodes the given `user_ids` into recipient slug
    string that can be used to construct a narrow URL.

    e.g., [13, 23, 9] -> "13,23,9-group"

    The `with_operator` parameter decides whether to append
    the "dm" operator to the recipient slug or not.

    e.g., "dm/13,23,9-group"

    """
    assert len(user_ids) > 0

    # For 3 or more user ids we use the "-group" decoration tag.
    # If we're only working with 1-2 user ids, it's either a
    # one-on-one direct message or direct message to ones self.
    # In this case, we don't include any decoration tag to the
    # slug.
    decoration_tag = ""
    if len(user_ids) >= 3:
        decoration_tag = "-group"

    direct_message_slug = ",".join([str(user_id) for user_id in sorted(user_ids)]) + decoration_tag
    if with_operator:
        return f"dm/{direct_message_slug}"
    return direct_message_slug


def encode_user_full_name_and_id(full_name: str, user_id: int, with_operator: bool = False) -> str:
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
    direct_message_slug = str(user_id) + "-" + encoded_user_name
    if with_operator:
        return f"dm/{direct_message_slug}"
    return direct_message_slug


def personal_narrow_url(*, realm: Realm, sender: UserProfile) -> str:
    base_url = f"{realm.url}/#narrow/dm/"
    direct_message_slug = encode_user_full_name_and_id(sender.full_name, sender.id)
    return base_url + direct_message_slug


def direct_message_group_narrow_url(
    *, user: UserProfile, display_recipient: list[UserDisplayRecipient]
) -> str:
    realm = user.realm
    other_user_ids = [r["id"] for r in display_recipient if r["id"] != user.id]
    direct_message_slug = encode_user_ids(other_user_ids)
    base_url = f"{realm.url}/#narrow/dm/"
    return base_url + direct_message_slug


def stream_narrow_url(realm: Realm, stream: Stream) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return base_url + encode_channel(stream.id, stream.name)


def topic_narrow_url(*, realm: Realm, stream: Stream, topic_name: str) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return f"{base_url}{encode_channel(stream.id, stream.name)}/topic/{encode_hash_component(topic_name)}"


def message_link_url(
    realm: Realm, message: dict[str, Any], *, conversation_link: bool = False
) -> str:
    if message["type"] == "stream":
        url = stream_message_url(
            realm=realm,
            message=message,
            conversation_link=conversation_link,
        )
        return url

    url = pm_message_url(
        realm=realm,
        message=message,
        conversation_link=conversation_link,
    )
    return url


def stream_message_url(
    realm: Realm, message: dict[str, Any], *, conversation_link: bool = False
) -> str:
    if conversation_link:
        with_or_near = "with"
    else:
        with_or_near = "near"
    message_id = str(message["id"])
    stream_id = message["stream_id"]
    stream_name = message["display_recipient"]
    topic_name = get_topic_from_message_info(message)
    encoded_topic_name = encode_hash_component(topic_name)
    encoded_stream = encode_channel(stream_id, stream_name)

    parts = [
        realm.url,
        "#narrow",
        "channel",
        encoded_stream,
        "topic",
        encoded_topic_name,
        with_or_near,
        message_id,
    ]
    full_url = "/".join(parts)
    return full_url


def pm_message_url(
    realm: Realm, message: dict[str, Any], *, conversation_link: bool = False
) -> str:
    if conversation_link:
        with_or_near = "with"
    else:
        with_or_near = "near"

    message_id = str(message["id"])
    user_ids = [recipient["id"] for recipient in message["display_recipient"]]

    direct_message_slug = encode_user_ids(user_ids)

    parts = [
        realm.url,
        "#narrow",
        "dm",
        direct_message_slug,
        with_or_near,
        message_id,
    ]
    full_url = "/".join(parts)
    return full_url


def append_url_query_string(original_url: str, query: str) -> str:
    u = urlsplit(original_url)
    query = u.query + ("&" if u.query and query else "") + query
    return u._replace(query=query).geturl()
