from urllib.parse import quote, urlsplit

import re2

from zerver.lib.types import DisplayRecipientT, UserDisplayRecipient
from zerver.models import Realm, Stream, UserProfile


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


def near_message_url(
    realm: Realm,
    message_id: int,
    display_recipient: DisplayRecipientT,
    stream_id: int | None = None,
    topic_name: str | None = None,
) -> str:
    if stream_id:
        assert isinstance(display_recipient, str)
        url = near_stream_message_url(
            realm=realm,
            message_id=message_id,
            display_recipient=display_recipient,
            stream_id=stream_id,
            topic_name=topic_name,
        )
        return url
    assert not isinstance(display_recipient, str)
    url = near_pm_message_url(
        realm=realm, message_id=message_id, display_recipient=display_recipient
    )
    return url


def near_stream_message_url(
    realm: Realm,
    message_id: int,
    display_recipient: DisplayRecipientT,
    stream_id: int | None = None,
    topic_name: str | None = None,
) -> str:
    stream_id_ = int(str(stream_id))
    stream_name = str(display_recipient)
    encoded_topic_name = hash_util_encode(str(topic_name))
    encoded_stream = encode_stream(stream_id=stream_id_, stream_name=stream_name)

    parts = [
        realm.url,
        "#narrow",
        "channel",
        encoded_stream,
        "topic",
        encoded_topic_name,
        "near",
        str(message_id),
    ]
    full_url = "/".join(parts)
    return full_url


def near_pm_message_url(
    realm: Realm, message_id: int, display_recipient: list[UserDisplayRecipient]
) -> str:
    user_id_strings = [str(recipient["id"]) for recipient in display_recipient]

    # Use the "perma-link" format here that includes the sender's
    # user_id, so they're easier to share between people.
    pm_str = ",".join(user_id_strings) + "-pm"

    parts = [
        realm.url,
        "#narrow",
        "dm",
        pm_str,
        "near",
        str(message_id),
    ]
    full_url = "/".join(parts)
    return full_url


def append_url_query_string(original_url: str, query: str) -> str:
    u = urlsplit(original_url)
    query = u.query + ("&" if u.query and query else "") + query
    return u._replace(query=query).geturl()
