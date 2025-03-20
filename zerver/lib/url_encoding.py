from typing import Any, Literal
from urllib.parse import quote, urlsplit

import re2

from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.types import UserDisplayRecipient
from zerver.models import Message, Realm, Stream, UserProfile


def hash_util_encode(string: str) -> str:
    # Do the same encoding operation as shared internal_url.encodeHashComponent
    # on the frontend.
    # `safe` has a default value of "/", but we want those encoded, too.
    return quote(string, safe=b"").replace(".", "%2E").replace("%", ".")


def encode_stream(stream_id: int, stream_name: str) -> str:
    # We encode streams for urls as something like 99-Verona.
    stream_name = stream_name.replace(" ", "-")
    return str(stream_id) + "-" + hash_util_encode(stream_name)


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
    return base_url + encode_stream(stream.id, stream.name)


def topic_narrow_url(*, realm: Realm, stream: Stream, topic_name: str) -> str:
    base_url = f"{realm.url}/#narrow/channel/"
    return f"{base_url}{encode_stream(stream.id, stream.name)}/topic/{hash_util_encode(topic_name)}"


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
    encoded_topic_name = hash_util_encode(topic_name)
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
    str_user_ids = [str(recipient["id"]) for recipient in message["display_recipient"]]

    # Use the "perma-link" format here that includes the sender's
    # user_id, so they're easier to share between people.
    pm_str = ",".join(str_user_ids) + "-pm"

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


def get_message_narrow_link(
    message: Message,
    operator: Literal["near", "with"] = "near",
) -> str:
    from zerver.lib.url_decoding import Filter
    from zerver.models.recipients import Recipient, get_direct_message_group_user_ids

    realm = message.realm
    if message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        gdm_recipient = list(get_direct_message_group_user_ids(message.recipient))
        narrow_terms = [NarrowTerm("dm", gdm_recipient, False)]
    elif message.recipient.type == Recipient.PERSONAL:
        dm_recipient = message.recipient.type_id
        narrow_terms = [NarrowTerm("dm", dm_recipient, False)]
    else:
        assert message.recipient.type == Recipient.STREAM
        recipient = message.recipient.type_id
        topic_name = message.topic_name()
        narrow_terms = [
            NarrowTerm("channel", recipient, False),
            NarrowTerm("topic", topic_name, False),
        ]

    narrow_terms.append(NarrowTerm(operator, message.id, False))
    return Filter(narrow_terms, realm).generate_message_url()
