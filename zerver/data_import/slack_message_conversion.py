import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import zip_longest
from typing import Any, Literal, TypeAlias, TypedDict, cast
from xmlrpc.client import boolean

import regex
from django.core.exceptions import ValidationError
from requests.utils import requote_uri

from zerver.lib.markdown import get_markdown_link_for_url
from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.types import Validator
from zerver.lib.validator import (
    WildValue,
    check_anything,
    check_dict,
    check_int,
    check_list,
    check_string,
    check_string_in,
    check_url,
)

# stubs
ZerverFieldsT: TypeAlias = dict[str, Any]
SlackToZulipUserIDT: TypeAlias = dict[str, int]
AddedChannelsT: TypeAlias = dict[str, tuple[str, int]]
SlackFieldsT: TypeAlias = dict[str, Any]
ChannelMentionProcessorT: TypeAlias = Callable[[str], str | None]
UserMentionProcessorT: TypeAlias = Callable[[str], tuple[str, int] | None]


@dataclass
class RenderResult:
    content: str
    mentioned_user_ids: list[int]
    has_link: boolean


# Slack link can be in the format <http://www.foo.com|www.foo.com> and <http://foo.com/>
LINK_REGEX = r"""
              (<)                                                              # match '>'
              (http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/|ftp:\/\/)?  # protocol and www
                  ([a-z0-9]+([\-\.]{1}[a-z0-9]+)*)(\.)                         # domain name
                      ([a-z]{2,63}(:[0-9]{1,5})?)                              # domain
                  (\/[^>]*)?                                                   # path
              (\|)?(?:\|([^>]+))?                                # char after pipe (for Slack links)
              (>)
              """

SLACK_MAILTO_REGEX = r"""
                      <((mailto:)?                     # match  `<mailto:`
                      ([\w\.-]+@[\w\.-]+(\.[\w]+)+))   # match email
                          (\|)?                        # match pipe
                      ([\w\.-]+@[\w\.-]+(\.[\w]+)+)?>  # match email
                      """

SLACK_USERMENTION_REGEX = r"""
                           (<@)                  # Start with '<@'
                               ([a-zA-Z0-9]+)    # Here we have the Slack id
                           (\|)?                 # We not always have a vertical line in mention
                               ([a-zA-Z0-9]+)?   # If vertical line is present, this is short name
                           (>)                   # ends with '>'
                           """
# Slack doesn't have mid-word message-formatting like Zulip.
# Hence, ~stri~ke doesn't format the word in Slack, but ~~stri~~ke
# formats the word in Zulip
SLACK_STRIKETHROUGH_REGEX = r"""
                             (
                                # Capture punctuation (\p{P}), white space (\p{Zs}),
                                # symbols (\p{S}) or newline.
                                # Skip ~ to not reformat the same string twice
                                # Skip @ and \
                                # Skip closing brackets & closing quote (\p{Pf}\p{Pe})
                                (?![~`@\\\p{Pf}\p{Pe}])
                                [\p{P}\p{Zs}\p{S}]|^
                             )
                             (\~)                                  # followed by a ~
                                 ([^~]+)                           # any character except ~
                             (\~)                                  # followed by a ~
                             (
                                # Capture punctuation, white space, symbols or end of
                                # line.
                                # Skip ~ to not reformat the same string twice
                                # Skip @ and \
                                # Skip opening brackets & opening quote (\p{Pi}\p{Ps})
                                (?![~`@\\\p{Pi}\p{Ps}])
                                (?=[\p{P}\p{Zs}\p{S}]|$)
                             )
                             """
SLACK_ITALIC_REGEX = r"""
                      # Same as `SLACK_STRIKETHROUGH_REGEX`s. The difference
                      # being, this skips _ instead of ~
                      (
                        (?![_`@\\\p{Pf}\p{Pe}])
                        [\p{P}\p{Zs}\p{S}]|^
                      )
                      (\_)
                          ([^_]+)                    # any character except _
                      (\_)
                      (
                        (?![_`@\\\p{Pi}\p{Ps}])
                        (?=[\p{P}\p{Zs}\p{S}]|$)
                      )
                      """
SLACK_BOLD_REGEX = r"""
                    # Same as `SLACK_STRIKETHROUGH_REGEX`s. The difference
                    # being, this skips * instead of ~
                    (
                        (?![*`@\\\p{Pf}\p{Pe}])
                        [\p{P}\p{Zs}\p{S}]|^
                    )
                    (\*)
                        ([^*]+)                       # any character except *
                    (\*)
                    (
                        (?![*`@\\\p{Pi}\p{Ps}])
                        (?=[\p{P}\p{Zs}\p{S}]|$)
                    )
                    """


def get_user_full_name(user: ZerverFieldsT) -> str:
    if "deleted" in user and user["deleted"] is False:
        return user["real_name"] or user["name"]
    elif user["is_mirror_dummy"]:
        return user["profile"].get("real_name", user["name"])
    else:
        return user["name"]


def get_zulip_mention_for_slack_user(
    slack_user_id: str | None,
    slack_user_shortname: str | None,
    users: list[ZerverFieldsT],
    silent: bool = False,
) -> str | None:
    if slack_user_id:
        for user in users:
            if user["id"] == slack_user_id and (
                slack_user_shortname is None or user["name"] == slack_user_shortname
            ):
                return ("@_**" if silent else "@**") + get_user_full_name(user) + "**"
    return None


def get_user_mentions(
    token: str,
    users: list[ZerverFieldsT],
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
) -> tuple[str, int | None]:
    slack_usermention_match = re.search(SLACK_USERMENTION_REGEX, token, re.VERBOSE)
    assert slack_usermention_match is not None
    short_name = slack_usermention_match.group(4)
    slack_id = slack_usermention_match.group(2)
    zulip_mention = get_zulip_mention_for_slack_user(slack_id, short_name, users)
    if zulip_mention is not None:
        token = re.sub(SLACK_USERMENTION_REGEX, zulip_mention, token, flags=re.VERBOSE)
        user_id = slack_user_id_to_zulip_user_id[slack_id]
        return token, user_id
    return token, None


def convert_link_format(text: str) -> tuple[str, bool]:
    """
    1. Converts '<https://foo.com>' to 'https://foo.com'
    2. Converts '<https://foo.com|foo>' to '[foo](https://foo.com)'
    """
    has_link = False
    for match in re.finditer(LINK_REGEX, text, re.VERBOSE):
        slack_url = match.group(0)
        url_parts = slack_url[1:-1].split("|", maxsplit=1)
        # Check if there's a pipe with text after it
        if len(url_parts) == 2:
            converted_url = f"[{url_parts[1]}]({url_parts[0]})"
        else:
            converted_url = url_parts[0]

        has_link = True
        text = text.replace(slack_url, converted_url)
    return text, has_link


def convert_mailto_format(text: str) -> tuple[str, bool]:
    """
    1. Converts '<mailto:foo@foo.com>' to 'mailto:foo@foo.com'
    2. Converts '<mailto:foo@foo.com|foo@foo.com>' to 'mailto:foo@foo.com'
    """
    has_link = False
    for match in re.finditer(SLACK_MAILTO_REGEX, text, re.VERBOSE):
        has_link = True
        text = text.replace(match.group(0), match.group(1))
    return text, has_link


# Map italic, bold and strikethrough Markdown
def convert_markdown_syntax(text: str, pattern: str, zulip_keyword: str) -> str:
    """
    Returns:
    1. For strikethrough formatting: This maps Slack's '~strike~' to Zulip's '~~strike~~'
    2. For bold formatting: This maps Slack's '*bold*' to Zulip's '**bold**'
    3. For italic formatting: This maps Slack's '_italic_' to Zulip's '*italic*'
    """

    def replace_slack_format(match: regex.Match[str]) -> str:
        return match.group(1) + zulip_keyword + match.group(3) + zulip_keyword

    return regex.sub(pattern, replace_slack_format, text, flags=re.VERBOSE | re.MULTILINE)


def convert_slack_workspace_mentions(text: str) -> str:
    # Map Slack's '<!everyone>', '<!channel>' and '<!here>'
    # mentions to Zulip's '@**all**' wildcard mention.
    # No regex for these as they can be present anywhere
    # in the sentence.
    text = text.replace("<!everyone>", "@**all**")
    text = text.replace("<!channel>", "@**all**")
    text = text.replace("<!here>", "@**all**")
    return text


def convert_slack_formatting(text: str) -> tuple[str, bool]:
    text = convert_markdown_syntax(text, SLACK_BOLD_REGEX, "**")
    text = convert_markdown_syntax(text, SLACK_STRIKETHROUGH_REGEX, "~~")
    text = convert_markdown_syntax(text, SLACK_ITALIC_REGEX, "*")
    # Check and convert link format
    text, has_link = convert_link_format(text)
    # convert `<mailto:foo@foo.com>` to `mailto:foo@foo.com`
    text, has_mailto_link = convert_mailto_format(text)
    return text, has_link or has_mailto_link


# Markdown mapping
def convert_to_zulip_markdown(
    text: str,
    users: list[ZerverFieldsT],
    added_channels: AddedChannelsT,
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
) -> tuple[str, list[int], bool]:
    mentioned_users_id = []
    text, message_has_link = convert_slack_formatting(text)
    text = convert_slack_workspace_mentions(text)

    # Map Slack channel mention: '<#C5Z73A7RA|general>' to '#**general**'
    for cname, ids in added_channels.items():
        cid = ids[0]
        text = text.replace(f"<#{cid}|{cname}>", "#**" + cname + "**")

    tokens = text.split(" ")
    for iterator in range(len(tokens)):
        # Check user mentions and change mention format from
        # '<@slack_id|short_name>' to '@**full_name**'
        if re.findall(SLACK_USERMENTION_REGEX, tokens[iterator], re.VERBOSE):
            tokens[iterator], user_id = get_user_mentions(
                tokens[iterator], users, slack_user_id_to_zulip_user_id
            )
            if user_id is not None:
                mentioned_users_id.append(user_id)

    text = " ".join(tokens)

    return text, mentioned_users_id, message_has_link


class LossyConversionError(Exception):
    pass


def render_rich_text_inline_style(element: WildValue, text: str) -> str:
    if "style" not in element:
        return text

    # Whitespace between words is included as part of the rich_text block of the text
    # to the right of it. Pull out trailing whitespace in each rich_text block to
    # render rich_text with text formatting/styles properly.
    stripped = text.rstrip()
    trailing_whitespace = text[len(stripped) :]
    text = stripped

    element_style = element["style"]
    with contextlib.suppress(ValidationError):
        if text.strip() != "":
            # The order is important. Other formatting syntaxes cannot be inside an
            # inline code block (backticks).
            if "code" in element_style:
                text = f"`{text}`"
            if "bold" in element_style:
                text = f"**{text}**"
            if "italic" in element_style:
                text = f"*{text}*"
            if "strike" in element_style:
                text = f"~~{text}~~"
    text += trailing_whitespace
    return text


def render_rich_text_element(
    element: WildValue,
    channel_mention_processor: ChannelMentionProcessorT,
    user_mention_processor: UserMentionProcessorT,
) -> RenderResult:
    element_type = element["type"].tame(check_string)
    has_link = False
    mentioned_user_ids = []
    match element_type:
        case "rich_text_section":
            # This element is composed of "text", "link", or "emoji" elements.
            # A "rich_text_section" as a sentence looks something like this
            # (each [{text}] is a rich text element):
            #
            # "[bold text here ][followed by some basic texts, ][some italic text, ]
            # [an inline code][ , etc.\n]"
            pieces = []
            for sub_element in element["elements"]:
                result = render_rich_text_element(
                    sub_element, channel_mention_processor, user_mention_processor
                )
                pieces.append(result.content)
                if result.has_link:
                    has_link = True
                mentioned_user_ids += result.mentioned_user_ids
            text = "".join(piece for piece in pieces)
        case "rich_text_list":
            # This element is a list.
            pieces = []
            for sub_element in element["elements"]:
                result = render_rich_text_element(
                    sub_element, channel_mention_processor, user_mention_processor
                )
                pieces.append(result.content)
                if result.has_link:
                    has_link = True
                mentioned_user_ids += result.mentioned_user_ids
            list_style = element["style"].tame(check_string_in(["ordered", "bullet"]))
            list_syntax = "1." if list_style == "ordered" else "-"
            indent_depth = element["indent"].tame(check_int)
            # We start to reliably render a list item as a sub list item at 3 or
            # more indents/white spaces.
            indents = " " * 3 * indent_depth if indent_depth > 0 else ""
            text = "".join(f"{indents}{list_syntax} {piece}\n" for piece in pieces).rstrip()
        case "rich_text_quote":
            # This element is a quote block.
            pieces = []
            for sub_element in element["elements"]:
                result = render_rich_text_element(
                    sub_element, channel_mention_processor, user_mention_processor
                )
                pieces.append(result.content)
            quote_content = "".join(piece for piece in pieces)
            fence = get_unused_fence(quote_content)
            text = f"{fence}quote\n{quote_content}\n{fence}"
        case "rich_text_preformatted":
            # This is a code block, it should contain exactly one "text" element.
            assert len(element["elements"]) == 1
            code_block_content = element["elements"][0]["text"].tame(check_string)
            fence = get_unused_fence(code_block_content)
            # Slack code block is programming language agnostic.
            text = f"{fence}text\n{code_block_content}\n{fence}"
        case "text":
            text = element["text"].tame(check_string)
            text = render_rich_text_inline_style(element, text)
        case "link":
            text = element["text"].tame(check_string)
            text = get_markdown_link_for_url(text, element["url"].tame(check_string))
            has_link = True
            text = render_rich_text_inline_style(element, text)
        case "emoji":
            emoji_name = element["name"].tame(check_string)
            text = f":{emoji_name}:"
        case "user":
            slack_user_id = element["user_id"].tame(check_string)
            if mention_result := user_mention_processor(slack_user_id):
                user_mention, zulip_user_id = mention_result
                text = user_mention
                mentioned_user_ids.append(zulip_user_id)
            else:
                text = f"**#Unknown Slack user {slack_user_id}**"
        case "channel":
            slack_channel_id = element["channel_id"].tame(check_string)
            channel_mention = channel_mention_processor(slack_channel_id)
            text = channel_mention or f"**#Unknown Slack channel {slack_channel_id}**"
        case "broadcast":
            if element["range"].tame(check_string) in ["here", "everyone", "channel"]:
                text = "@**all**"
        case "canvas":
            # This is attached files, both the Slack importer and webhook integration
            # have a different way of handling files, so we don't need to do anything
            # special here.
            text = ""
        case _:
            raise LossyConversionError(
                f"Unknown rich_text block: {element_type}.\n{element.tame(check_anything)}"
            )
    return RenderResult(
        content=text,
        mentioned_user_ids=mentioned_user_ids,
        has_link=has_link,
    )


def render_block(
    block: WildValue,
    channel_mention_processor: ChannelMentionProcessorT,
    user_mention_processor: UserMentionProcessorT,
) -> RenderResult:
    """
    Raises `LossyConversionError` if it's a rich_text block type.
    """
    # https://api.slack.com/reference/block-kit/blocks
    supported_types = {
        "context",
        "divider",
        "header",
        "image",
        "section",
        "rich_text",
    }
    unhandled_types = {
        # `call` is a block type we've observed in the wild in a Slack export,
        # despite not being documented in
        # https://docs.slack.dev/reference/block-kit/blocks/
        # It likes maps to a request for a Slack call. If we can verify that,
        # probably it would be worth replacing with a string indicating a Slack
        # call occurred.
        "call",
        "contact_card",
        "file",
        "table",
        # The "actions" block is used to format literal in-message clickable
        # buttons and similar elements, which Zulip currently doesn't support.
        # https://docs.slack.dev/reference/block-kit/blocks/actions-block
        "actions",
        "input",
        "condition",
    }
    known_types = {
        *supported_types,
        *unhandled_types,
    }
    block_type = block["type"].tame(check_string_in(known_types))

    content: str = ""
    has_link = False
    mentioned_user_ids = []
    if block_type in unhandled_types:
        content = ""
    elif block_type == "rich_text":
        pieces = []
        for sub_element in block["elements"]:
            result = render_rich_text_element(
                sub_element, channel_mention_processor, user_mention_processor
            )
            pieces.append(result.content)
            if result.has_link:
                has_link = True
            mentioned_user_ids += result.mentioned_user_ids
        content = "\n".join(piece for piece in pieces if piece.strip() != "")
    elif block_type == "context" and block.get("elements"):
        pieces = []
        # Slack renders these pieces left-to-right, packed in as
        # closely as possible.  We just render them above each other,
        # for simplicity.
        for element in block["elements"]:
            element_type = element["type"].tame(check_string_in(["image", "plain_text", "mrkdwn"]))
            if element_type == "image":
                pieces.append(render_block_element(element))
            else:
                text_field = element.tame(check_text_block())
                text, block_has_link = convert_slack_formatting(text_field["text"])
                has_link = has_link or block_has_link
                pieces.append(text)
        content = "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")
    elif block_type == "divider":
        content = "----"
    elif block_type == "header":
        content = "## " + block["text"].tame(check_text_block(plain_text_only=True))["text"]
    elif block_type == "image":
        image_url = block["image_url"].tame(check_url)
        alt_text = block["alt_text"].tame(check_string)
        if "title" in block:
            alt_text = block["title"].tame(check_text_block(plain_text_only=True))["text"]
        content = f"[{alt_text}]({image_url})"
        has_link = True
    elif block_type == "section":
        pieces = []
        if "text" in block:
            text_field = block["text"].tame(check_text_block())
            text, block_has_link = convert_slack_formatting(text_field["text"])
            has_link = has_link or block_has_link
            pieces.append(text)
        if "accessory" in block:
            pieces.append(render_block_element(block["accessory"]))

        if "fields" in block:
            fields = block["fields"].tame(check_list(check_text_block()))
            if len(fields) == 1:
                # Special-case a single field to display a bit more
                # nicely, without extraneous borders and limitations
                # on its contents.
                text, block_has_link = convert_slack_formatting(fields[0]["text"])
                has_link = has_link or block_has_link
                pieces.append(text)
            else:
                # It is not possible to have newlines in a table, nor
                # escape the pipes that make it up; replace them with
                # whitespace.
                field_text = [f["text"].replace("\n", " ").replace("|", " ") for f in fields]
                # Because Slack formats this as two columns, but not
                # necessarily a table with a bold header, we emit a
                # blank header row first.
                table = "| | |\n|-|-|\n"
                # Then take the fields two-at-a-time to make the table
                iters = [iter(field_text)] * 2
                for left, right in zip_longest(*iters, fillvalue=""):
                    table += f"| {left} | {right} |\n"
                pieces.append(table)

        content = "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")

    return RenderResult(content=content, mentioned_user_ids=mentioned_user_ids, has_link=has_link)


class TextField(TypedDict):
    text: str
    type: Literal["plain_text", "mrkdwn"]


def check_text_block(plain_text_only: bool = False) -> Validator[TextField]:
    if plain_text_only:
        type_validator = check_string_in(["plain_text"])
    else:
        type_validator = check_string_in(["plain_text", "mrkdwn"])

    def f(var_name: str, val: object) -> TextField:
        block = check_dict(
            [
                ("type", type_validator),
                ("text", check_string),
            ],
        )(var_name, val)

        return cast(TextField, block)

    return f


def render_block_element(element: WildValue) -> str:
    # https://api.slack.com/reference/block-kit/block-elements
    # Zulip doesn't support interactive elements, so we only render images here
    element_type = element["type"].tame(check_string)
    if element_type == "image":
        try:
            image_url = element["image_url"].tame(check_url)
            alt_text = element["alt_text"].tame(check_string)
            return f"[{alt_text}]({image_url})"
        except ValidationError:
            # Just drop invalid image URLs, rather than drop the whole message.
            return ""
    else:
        # Unsupported
        return ""


def render_attachment(
    attachment: WildValue,
    channel_mention_processor: ChannelMentionProcessorT,
    user_mention_processor: UserMentionProcessorT,
) -> RenderResult:
    # https://api.slack.com/reference/messaging/attachments
    # Slack recommends the usage of "blocks" even within attachments; the
    # rest of the fields we handle here are legacy fields. These fields are
    # optional and may contain null values.
    pieces = []
    has_link = False
    mentioned_user_ids = []
    if attachment.get("title"):
        title = attachment["title"].tame(check_string)
        if attachment.get("title_link"):
            title_link = attachment["title_link"].tame(check_url)
            pieces.append(f"## [{title}]({title_link})")
        else:
            pieces.append(f"## {title}")
    if attachment.get("pretext"):
        pieces.append(attachment["pretext"].tame(check_string))
    if attachment.get("text"):
        text, has_link = convert_slack_formatting(attachment["text"].tame(check_string))
        pieces.append(text)
    if "fields" in attachment:
        fields = []
        for field in attachment["fields"]:
            if "title" in field and "value" in field and field["title"] and field["value"]:
                title = field["title"].tame(check_string)
                value = field["value"].tame(check_string)
                fields.append(f"**{title}**: {value}")
            elif field.get("title"):
                title = field["title"].tame(check_string)
                fields.append(f"**{title}**")
            elif field.get("value"):
                value = field["value"].tame(check_string)
                fields.append(f"{value}")
        pieces.append("\n".join(fields))
    if attachment.get("blocks"):
        for block in attachment["blocks"]:
            result = render_block(block, channel_mention_processor, user_mention_processor)
            pieces.append(result.content)
            if result.has_link:
                has_link = True
            mentioned_user_ids += result.mentioned_user_ids
    if image_url_wv := attachment.get("image_url"):
        try:
            image_url = image_url_wv.tame(check_url)
        except ValidationError:  # nocoverage
            image_url = image_url_wv.tame(check_string)
            image_url = requote_uri(image_url)
        pieces.append(f"[]({image_url})")
        has_link = True
    if attachment.get("footer"):
        pieces.append(attachment["footer"].tame(check_string))
    if attachment.get("ts"):
        try:
            time = attachment["ts"].tame(check_int)
        except ValidationError as e:  # nocoverage
            # In some cases Slack has the ts as a string with a float
            # number. The reason is unknown, but we've observed it
            # in the wild several times.
            ts = attachment["ts"].tame(check_string)
            try:
                ts_float = float(ts)
            except ValueError:
                raise e

            time = int(ts_float)
        pieces.append(datetime_to_global_time(datetime.fromtimestamp(time, timezone.utc)))

    return RenderResult(
        content="\n\n".join(piece.strip() for piece in pieces if piece.strip() != ""),
        mentioned_user_ids=mentioned_user_ids,
        has_link=has_link,
    )


def replace_links(text: str) -> str:
    text, _ = convert_link_format(text)
    text, _ = convert_mailto_format(text)
    return text


def process_slack_block_and_attachment(
    message: WildValue,
    channel_mention_processor: ChannelMentionProcessorT,
    user_mention_processor: UserMentionProcessorT,
) -> RenderResult:
    pieces: list[str] = []
    has_link = False
    mentioned_user_ids = []
    raw_text = message["text"].tame(check_string)

    if message.get("blocks"):
        for block in message["blocks"]:
            result = render_block(block, channel_mention_processor, user_mention_processor)
            pieces.append(result.content)
            if result.has_link:
                has_link = True
            mentioned_user_ids += result.mentioned_user_ids

    # This is primarily for payloads like zerver/webhooks/slack/fixtures/message_with_variety_files.json
    # where the message contains the "text" field but no "blocks" field.
    # Although, upon trying to recreate the message data again, it seems
    # to have generated proper "blocks" for any text the message might
    # have, so for the most part this is just an extra safe guard.
    # See test_variety_files_and_rich_text in test_slack_message_conversion.py.
    if set(pieces) in ({""}, set()) and raw_text:
        text, text_has_link = convert_slack_formatting(raw_text)
        has_link = has_link or text_has_link
        pieces.append(text)

    if message.get("attachments"):
        for attachment in message["attachments"]:
            result = render_attachment(
                attachment, channel_mention_processor, user_mention_processor
            )
            pieces.append(result.content)
            if result.has_link:
                has_link = True
            mentioned_user_ids += result.mentioned_user_ids
    return RenderResult(
        content="\n".join(piece.strip() for piece in pieces if piece.strip() != ""),
        mentioned_user_ids=mentioned_user_ids,
        has_link=has_link,
    )
