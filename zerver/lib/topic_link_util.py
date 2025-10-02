# Keep this synchronized with web/src/topic_link_util.ts

import re

from zerver.lib.url_encoding import encode_channel, encode_hash_component
from zerver.models.messages import Message

invalid_stream_topic_regex = re.compile(r"[`>*&\[\]]|(\$\$)")


def will_produce_broken_stream_topic_link(word: str) -> bool:
    return bool(invalid_stream_topic_regex.search(word))


escape_mapping = {
    "`": "&#96;",
    ">": "&gt;",
    "*": "&#42;",
    "&": "&amp;",
    "$$": "&#36;&#36;",
    "[": "&#91;",
    "]": "&#93;",
}


def escape_invalid_stream_topic_characters(text: str) -> str:
    return re.sub(
        invalid_stream_topic_regex,
        lambda match: escape_mapping.get(match.group(0), match.group(0)),
        text,
    )


def get_fallback_markdown_link(
    stream_id: int, stream_name: str, topic_name: str | None = None, message_id: int | None = None
) -> str:
    """
    Helper that should only be called by other methods in this file.

    Generates the vanilla markdown link syntax for a stream/topic/message link, as
    a fallback for cases where the nicer Zulip link syntax would not
    render properly due to special characters in the channel or topic name.
    """
    escape = escape_invalid_stream_topic_characters
    link = f"#narrow/channel/{encode_channel(stream_id, stream_name)}"
    text = f"#{escape(stream_name)}"
    if topic_name is not None:
        link += f"/topic/{encode_hash_component(topic_name)}"
        if topic_name == "":
            topic_name = Message.EMPTY_TOPIC_FALLBACK_NAME
        text += f" > {escape(topic_name)}"

    if message_id is not None:
        link += f"/near/{message_id}"
        text += " @ 💬"

    return f"[{text}]({link})"


def get_message_link_syntax(
    stream_id: int, stream_name: str, topic_name: str, message_id: int
) -> str:
    # If the stream/topic name is such that it will
    # generate an invalid #**stream>topic@message_id** syntax,
    # we revert to generating the normal markdown syntax for a link.
    if will_produce_broken_stream_topic_link(topic_name) or will_produce_broken_stream_topic_link(
        stream_name
    ):
        return get_fallback_markdown_link(stream_id, stream_name, topic_name, message_id)
    return f"#**{stream_name}>{topic_name}@{message_id}**"


def get_stream_topic_link_syntax(stream_id: int, stream_name: str, topic_name: str) -> str:
    # If the stream/topic name is such that it will generate an invalid #**stream>topic** syntax,
    # we revert to generating the normal markdown syntax for a link.
    if will_produce_broken_stream_topic_link(topic_name) or will_produce_broken_stream_topic_link(
        stream_name
    ):
        return get_fallback_markdown_link(stream_id, stream_name, topic_name)
    return f"#**{stream_name}>{topic_name}**"


def get_stream_link_syntax(stream_id: int, stream_name: str) -> str:
    # If the stream name is such that it will generate an invalid #**stream** syntax,
    # we revert to generating the normal markdown syntax for a link.
    if will_produce_broken_stream_topic_link(stream_name):
        return get_fallback_markdown_link(stream_id, stream_name)
    return f"#**{stream_name}**"
