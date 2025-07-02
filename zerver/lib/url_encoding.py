from typing import Any
from urllib.parse import quote, urlsplit

import re2

from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.types import UserDisplayRecipient
from zerver.models import Realm, Stream, UserProfile


def hash_util_encode(string: str) -> str:
    # Do the same encoding operation as shared internal_url.encodeHashComponent
    # on the frontend.
    # `safe` has a default value of "/", but we want those encoded, too.
    return quote(string, safe=b"").replace(".", "%2E").replace("%", ".")


def encode_channel(channel_id: int, channel_name: str) -> str:
    # We encode channel for urls as something like 99-Verona.
    channel_name = channel_name.replace(" ", "-")
    return str(channel_id) + "-" + hash_util_encode(channel_name)


def personal_narrow_url(*, realm: Realm, sender: UserProfile) -> str:
    base_url = f"{realm.url}/#narrow/dm/"
    encoded_user_name = re2.sub(r'[ "%\/<>`\p{C}]+', "-", sender.full_name)
    pm_slug = str(sender.id) + "-" + encoded_user_name
    return base_url + pm_slug


def direct_message_group_narrow_url(
    *, user: UserProfile, display_recipient: list[UserDisplayRecipient]
) -> str:
    realm = user.realm
    other_user_ids = [r["id"] for r in display_recipient if r["id"] != user.id]
    pm_slug = ",".join(str(user_id) for user_id in sorted(other_user_ids)) + "-group"
    base_url = f"{realm.url}/#narrow/dm/"
    return base_url + pm_slug


def stream_narrow_url(realm: Realm, stream: Stream) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return base_url + encode_channel(stream.id, stream.name)


def topic_narrow_url(*, realm: Realm, stream: Stream, topic_name: str) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return (
        f"{base_url}{encode_channel(stream.id, stream.name)}/topic/{hash_util_encode(topic_name)}"
    )


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
    encoded_topic_name = hash_util_encode(topic_name)
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
    str_user_ids = [str(recipient["id"]) for recipient in message["display_recipient"]]

    # Use the "perma-link" format here that includes the sender's
    # user_id, so they're easier to share between people.
    pm_str = ",".join(str_user_ids) + "-pm"

    parts = [
        realm.url,
        "#narrow",
        "dm",
        pm_str,
        with_or_near,
        message_id,
    ]
    full_url = "/".join(parts)
    return full_url


def append_url_query_string(original_url: str, query: str) -> str:
    u = urlsplit(original_url)
    query = u.query + ("&" if u.query and query else "") + query
    return u._replace(query=query).geturl()
