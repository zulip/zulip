# Keep this synchronized with web/src/topic_link_util.ts

import re
import urllib.parse

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


hash_replacements = {
    "%": ".",
    "(": ".28",
    ")": ".29",
    ".": ".2E",
}


def encode_hash_component(s: str) -> str:
    encoded = urllib.parse.quote(s, safe="*")
    return "".join(hash_replacements.get(c, c) for c in encoded)


def channel_topic_url(stream_id: int, stream_name: str, topic_name: str | None = None) -> str:
    link = f"#narrow/channel/{stream_id}-{encode_hash_component(stream_name.replace(' ', '-'))}"
    if topic_name:
        link += f"/topic/{encode_hash_component(topic_name)}"
    return link


def get_fallback_markdown_link(
    stream_id: int, stream_name: str, topic_name: str | None = None
) -> str:
    """
    Generates the markdown link syntax for a stream or topic link.
    """
    escape = escape_invalid_stream_topic_characters
    url = channel_topic_url(stream_id, stream_name, topic_name)
    if topic_name:
        return f"[#{escape(stream_name)} > {escape(topic_name)}]({url})"

    return f"[#{escape(stream_name)}]({url})"


def get_stream_topic_link_syntax(stream_id: int, stream_name: str, topic_name: str) -> str:
    # If the topic name is such that it will generate an invalid #**stream>topic** syntax,
    # we revert to generating the normal markdown syntax for a link.
    if will_produce_broken_stream_topic_link(topic_name) or will_produce_broken_stream_topic_link(
        stream_name
    ):
        return get_fallback_markdown_link(stream_id, stream_name, topic_name)
    return f"#**{stream_name}>{topic_name}**"


def get_stream_link_syntax(stream_id: int, stream_name: str) -> str:
    # If the topic name is such that it will generate an invalid #**stream>topic** syntax,
    # we revert to generating the normal markdown syntax for a link.
    if will_produce_broken_stream_topic_link(stream_name):
        return get_fallback_markdown_link(stream_id, stream_name)
    return f"#**{stream_name}**"
