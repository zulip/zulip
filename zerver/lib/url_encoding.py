import urllib.parse
from typing import Any
from urllib.parse import urlsplit

import re2

from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.types import UserDisplayRecipient
from zerver.models import Message, Realm, Recipient, Stream, UserProfile

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
    channel_name = channel_name.replace(" ", "-")
    encoded_channel = str(channel_id) + "-" + encode_hash_component(channel_name)
    if with_operator:
        return f"channel/{encoded_channel}"
    return encoded_channel


def encode_user_ids(user_ids: list[int], with_operator: bool = False) -> str:
    assert len(user_ids) > 0
    decoration_tag = ""
    if len(user_ids) >= 3:
        decoration_tag = "-group"
    direct_message_slug = ",".join([str(user_id) for user_id in sorted(user_ids)]) + decoration_tag
    if with_operator:
        return f"dm/{direct_message_slug}"
    return direct_message_slug


def encode_user_full_name_and_id(full_name: str, user_id: int, with_operator: bool = False) -> str:
    encoded_user_name = re2.sub(r'[ "%\/<>`\p{C}]+', "-", full_name.strip())
    direct_message_slug = str(user_id) + "-" + encoded_user_name
    if with_operator:
        return f"dm/{direct_message_slug}"
    return direct_message_slug


def personal_narrow_url(*, realm: Realm, sender_id: int, sender_full_name: str) -> str:
    base_url = f"{realm.url}/#narrow/dm/"
    direct_message_slug = encode_user_full_name_and_id(sender_full_name, sender_id)
    return base_url + direct_message_slug


def direct_message_group_narrow_url(
    *, user: UserProfile, display_recipient: list[UserDisplayRecipient]
) -> str:
    realm = user.realm
    if len(display_recipient) == 1:
        return personal_narrow_url(realm=realm, sender_id=user.id, sender_full_name=user.full_name)
    if len(display_recipient) == 2:
        other_user = next(r for r in display_recipient if r["id"] != user.id)
        return personal_narrow_url(
            realm=realm, sender_id=other_user["id"], sender_full_name=other_user["full_name"]
        )
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


# =============================================================================
# NEW Type-safe Message-based URL functions
#
# See https://github.com/zulip/zulip/issues/25021 for context.
# =============================================================================


def near_message_url(
    message: Message,
    *,
    user: UserProfile | None = None,
    conversation_link: bool = False,
) -> str:
    """
    Generate a URL linking to a specific message from a Message object.

    This is the preferred function for generating message URLs when you have
    a Message object. It is type-safe and does not require manual dict construction.

    Args:
        message: The Message object to link to.
        user: For DMs, the current user's perspective. Their ID will be excluded
              from the URL slug (matching direct_message_group_narrow_url behavior).
              This parameter is REQUIRED for DM messages to generate correct URLs.
        conversation_link: If True, uses "with" instead of "near" in the URL.

    Returns:
        A full URL string pointing to the message.
    """
    if message.recipient.type == Recipient.STREAM:
        return near_stream_message_url(message, conversation_link=conversation_link)
    return near_dm_message_url(message, user=user, conversation_link=conversation_link)


def near_stream_message_url(
    message: Message,
    *,
    conversation_link: bool = False,
) -> str:
    """
    Generate a URL for a channel (stream) message from a Message object.

    Args:
        message: The Message object (must be a channel message).
        conversation_link: If True, uses "with" instead of "near".

    Returns:
        A full URL string pointing to the channel message.
    """
    assert message.recipient.type == Recipient.STREAM

    realm = message.realm
    with_or_near = "with" if conversation_link else "near"
    message_id = str(message.id)

    stream_id = message.recipient.type_id
    stream = Stream.objects.only("name").get(id=stream_id)
    stream_name = stream.name

    topic_name = message.topic_name()
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
    return "/".join(parts)


def near_dm_message_url(
    message: Message,
    *,
    user: UserProfile | None = None,
    conversation_link: bool = False,
) -> str:
    """
    Generate a URL for a direct message from a Message object.

    Args:
        message: The Message object (must be a direct message).
        user: The current user's perspective. If provided, their ID is excluded
              from the URL slug, matching direct_message_group_narrow_url() behavior.
        conversation_link: If True, uses "with" instead of "near".

    Returns:
        A full URL string pointing to the direct message.
    """
    assert message.recipient.type in (Recipient.PERSONAL, Recipient.DIRECT_MESSAGE_GROUP)

    realm = message.realm
    with_or_near = "with" if conversation_link else "near"
    message_id = str(message.id)

    from zerver.lib.display_recipient import get_display_recipient

    # Get all user IDs in this DM conversation using display_recipient
    recipients = get_display_recipient(message.recipient)
    all_user_ids: list[int] = [r["id"] for r in recipients]

    # Filter out the current user's ID if provided (matching direct_message_group_narrow_url)
    if user is not None:
        user_ids = [uid for uid in all_user_ids if uid != user.id]
        # If filtering removed all IDs (shouldn't happen), fall back to all IDs
        if not user_ids:
            user_ids = all_user_ids
    else:
        user_ids = all_user_ids

    direct_message_slug = encode_user_ids(user_ids)

    parts = [
        realm.url,
        "#narrow",
        "dm",
        direct_message_slug,
        with_or_near,
        message_id,
    ]
    return "/".join(parts)


# =============================================================================
# Legacy dict-based URL functions (backward compatibility)
#
# These functions accept message dictionaries and are kept for backward
# compatibility with existing code. New code should prefer the type-safe
# Message-based functions above.
# =============================================================================


def message_link_url(
    realm: Realm, message: dict[str, Any], *, conversation_link: bool = False
) -> str:
    """
    Generate a URL linking to a message from a message dict.

    Note: If you have a Message object, prefer using near_message_url() instead.
    """
    if message["type"] == "stream":
        return stream_message_url(
            realm=realm,
            message=message,
            conversation_link=conversation_link,
        )
    return pm_message_url(
        realm=realm,
        message=message,
        conversation_link=conversation_link,
    )


def stream_message_url(
    realm: Realm, message: dict[str, Any], *, conversation_link: bool = False
) -> str:
    """
    Generate a URL for a stream message from a message dict.

    Note: If you have a Message object, prefer using near_stream_message_url() instead.
    """
    with_or_near = "with" if conversation_link else "near"
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
    return "/".join(parts)


def pm_message_url(
    realm: Realm, message: dict[str, Any], *, conversation_link: bool = False
) -> str:
    """
    Generate a URL for a direct message from a message dict.

    Note: If you have a Message object, prefer using near_dm_message_url() instead.
    """
    with_or_near = "with" if conversation_link else "near"
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
    return "/".join(parts)


def append_url_query_string(original_url: str, query: str) -> str:
    u = urlsplit(original_url)
    query = u.query + ("&" if u.query and query else "") + query
    return u._replace(query=query).geturl()
