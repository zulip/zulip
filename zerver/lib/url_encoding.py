from typing import Any, Dict, List
from urllib.parse import quote, urlsplit

import re2

from zerver.lib.topic import get_topic_from_message_info
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


def personal_narrow_url(realm: Realm, sender: UserProfile) -> str:
    base_url = f"{realm.uri}/#narrow/pm-with/"
    encoded_user_name = re2.sub(r'[ "%\/<>`\p{C}]+', "-", sender.full_name)
    pm_slug = str(sender.id) + "-" + encoded_user_name
    return base_url + pm_slug


def huddle_narrow_url(realm: Realm, other_user_ids: List[int]) -> str:
    pm_slug = ",".join(str(user_id) for user_id in sorted(other_user_ids)) + "-group"
    base_url = f"{realm.uri}/#narrow/pm-with/"
    return base_url + pm_slug


def stream_narrow_url(realm: Realm, stream: Stream) -> str:
    base_url = f"{realm.uri}/#narrow/stream/"
    return base_url + encode_stream(stream.id, stream.name)


def topic_narrow_url(realm: Realm, stream: Stream, topic: str) -> str:
    base_url = f"{realm.uri}/#narrow/stream/"
    return f"{base_url}{encode_stream(stream.id, stream.name)}/topic/{hash_util_encode(topic)}"


def near_message_url(realm: Realm, message: Dict[str, Any]) -> str:
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


def near_stream_message_url(realm: Realm, message: Dict[str, Any]) -> str:
    message_id = str(message["id"])
    stream_id = message["stream_id"]
    stream_name = message["display_recipient"]
    topic_name = get_topic_from_message_info(message)
    encoded_topic = hash_util_encode(topic_name)
    encoded_stream = encode_stream(stream_id=stream_id, stream_name=stream_name)

    parts = [
        realm.uri,
        "#narrow",
        "stream",
        encoded_stream,
        "topic",
        encoded_topic,
        "near",
        message_id,
    ]
    full_url = "/".join(parts)
    return full_url


def near_pm_message_url(realm: Realm, message: Dict[str, Any]) -> str:
    message_id = str(message["id"])
    str_user_ids = [str(recipient["id"]) for recipient in message["display_recipient"]]

    # Use the "perma-link" format here that includes the sender's
    # user_id, so they're easier to share between people.
    pm_str = ",".join(str_user_ids) + "-pm"

    parts = [
        realm.uri,
        "#narrow",
        "pm-with",
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
