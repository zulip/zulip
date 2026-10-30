import re


def convert_user_mention(
    content: str,
    user_id_to_fullname: dict[str, str],
    user_id_to_zulip_id: dict[str, int],
    mentioned_user_ids: set[int],
) -> str:
    """Convert Discord <@user_id> and <@!user_id> to Zulip @_**Full Name**.

    Uses silent mentions (@_**) since import notifications don't make
    sense in the import context.
    """

    def replace_mention(match: re.Match[str]) -> str:
        discord_user_id = match.group(1)
        if discord_user_id in user_id_to_fullname:
            full_name = user_id_to_fullname[discord_user_id]
            if discord_user_id in user_id_to_zulip_id:
                mentioned_user_ids.add(user_id_to_zulip_id[discord_user_id])
            return f"@_**{full_name}**"
        return match.group(0)

    return re.sub(r"<@!?(\d+)>", replace_mention, content)


def convert_channel_mention(
    content: str,
    channel_id_to_name: dict[str, str],
) -> str:
    """Convert Discord <#channel_id> to Zulip #**channel_name**."""

    def replace_channel(match: re.Match[str]) -> str:
        channel_id = match.group(1)
        if channel_id in channel_id_to_name:
            return f"#**{channel_id_to_name[channel_id]}**"
        return match.group(0)

    return re.sub(r"<#(\d+)>", replace_channel, content)


def convert_custom_emoji(content: str) -> str:
    """Convert Discord <:name:id> and <a:name:id> to Zulip :name:."""
    return re.sub(r"<a?:(\w+):\d+>", r":\1:", content)


def convert_role_mention(content: str) -> str:
    """Convert Discord <@&role_id> to plain text.

    TODO: Map Discord role mentions to Zulip user groups once
    the import framework supports group mapping.
    """
    return re.sub(r"<@&\d+>", "@role", content)


def convert_wildcard_mentions(content: str) -> str:
    """Convert Discord @everyone and @here to Zulip @**all**."""
    content = content.replace("@everyone", "@**all**")
    content = content.replace("@here", "@**all**")
    return content


def convert_underscore_italic(content: str) -> str:
    """Convert Discord _italic_ to Zulip *italic*.

    Discord supports both *italic* and _italic_. Zulip uses *italic*
    for italics. We only convert the underscore variant since *italic*
    already works in Zulip.
    """
    return re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"*\1*", content)


def convert_spoiler(content: str) -> str:
    """Convert Discord ||spoiler|| to Zulip spoiler block syntax."""
    return re.sub(r"\|\|(.+?)\|\|", r"```spoiler\n\1\n```", content, flags=re.DOTALL)


def convert_multiline_quote(content: str) -> str:
    """Convert Discord >>> multiline quote to Zulip quote block.

    Discord's >>> quotes everything after it to the end of the message.
    """
    return re.sub(r"^>>>[ ]?(.+)", r"```quote\n\1\n```", content, flags=re.DOTALL | re.MULTILINE)


def convert_single_line_quote(content: str) -> str:
    """Convert Discord > single line quotes to Zulip format.

    Both Discord and Zulip use > for single line quotes, so this is a
    no-op. Included for documentation completeness.
    """
    return content


def convert_to_zulip_markdown(
    content: str,
    user_id_to_fullname: dict[str, str],
    user_id_to_zulip_id: dict[str, int],
    channel_id_to_name: dict[str, str],
) -> tuple[str, set[int], bool]:
    """Convert Discord markdown to Zulip markdown.

    Returns (converted_text, mentioned_user_ids, has_link).
    """
    mentioned_user_ids: set[int] = set()
    has_link = bool(re.search(r"https?://", content))

    content = convert_multiline_quote(content)
    content = convert_spoiler(content)
    content = convert_user_mention(
        content, user_id_to_fullname, user_id_to_zulip_id, mentioned_user_ids
    )
    content = convert_channel_mention(content, channel_id_to_name)
    content = convert_custom_emoji(content)
    content = convert_role_mention(content)
    content = convert_wildcard_mentions(content)
    content = convert_underscore_italic(content)

    has_wildcard = "@**all**" in content

    return content, mentioned_user_ids, has_link or has_wildcard
