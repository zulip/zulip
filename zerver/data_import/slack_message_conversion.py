import re
from itertools import zip_longest
from typing import Any, Literal, TypeAlias, TypedDict, cast

from zerver.lib.types import Validator
from zerver.lib.validator import (
    WildValue,
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
                             (^|[ -(]|[+-/]|\*|\_|[:-?]|\{|\[|\||\^)     # Start after specified characters
                             (\~)                                  # followed by an asterisk
                                 ([ -)+-}—]*)([ -}]+)              # any character except asterisk
                             (\~)                                  # followed by an asterisk
                             ($|[ -']|[+-/]|[:-?]|\*|\_|\}|\)|\]|\||\^)  # ends with specified characters
                             """
SLACK_ITALIC_REGEX = r"""
                      (^|[ -*]|[+-/]|[:-?]|\{|\[|\||\^|~)
                      (\_)
                          ([ -^`~—]*)([ -^`-~]+)                  # any character
                      (\_)
                      ($|[ -']|[+-/]|[:-?]|\}|\)|\]|\*|\||\^|~)
                      """
SLACK_BOLD_REGEX = r"""
                    (^|[ -(]|[+-/]|[:-?]|\{|\[|\_|\||\^|~)
                    (\*)
                        ([ -)+-~—]*)([ -)+-~]+)                   # any character
                    (\*)
                    ($|[ -']|[+-/]|[:-?]|\}|\)|\]|\_|\||\^|~)
                    """


def get_user_full_name(user: ZerverFieldsT) -> str:
    if "deleted" in user and user["deleted"] is False:
        return user["real_name"] or user["name"]
    elif user["is_mirror_dummy"]:
        return user["profile"].get("real_name", user["name"])
    else:
        return user["name"]


def get_user_mentions(
    token: str, users: list[ZerverFieldsT], slack_user_id_to_zulip_user_id: SlackToZulipUserIDT
) -> tuple[str, int | None]:
    slack_usermention_match = re.search(SLACK_USERMENTION_REGEX, token, re.VERBOSE)
    assert slack_usermention_match is not None
    short_name = slack_usermention_match.group(4)
    slack_id = slack_usermention_match.group(2)
    for user in users:
        if (user["id"] == slack_id and user["name"] == short_name and short_name) or (
            user["id"] == slack_id and short_name is None
        ):
            full_name = get_user_full_name(user)
            user_id = slack_user_id_to_zulip_user_id[slack_id]
            mention = "@**" + full_name + "**"
            token = re.sub(SLACK_USERMENTION_REGEX, mention, token, flags=re.VERBOSE)
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
def convert_markdown_syntax(text: str, regex: str, zulip_keyword: str) -> str:
    """
    Returns:
    1. For strikethrough formatting: This maps Slack's '~strike~' to Zulip's '~~strike~~'
    2. For bold formatting: This maps Slack's '*bold*' to Zulip's '**bold**'
    3. For italic formatting: This maps Slack's '_italic_' to Zulip's '*italic*'
    """
    for match in re.finditer(regex, text, re.VERBOSE):
        converted_token = (
            match.group(1)
            + zulip_keyword
            + match.group(3)
            + match.group(4)
            + zulip_keyword
            + match.group(6)
        )
        text = text.replace(match.group(0), converted_token)
    return text


def convert_slack_workspace_mentions(text: str) -> str:
    # Map Slack's '<!everyone>', '<!channel>' and '<!here>'
    # mentions to Zulip's '@**all**' wildcard mention.
    # No regex for these as they can be present anywhere
    # in the sentence.
    text = text.replace("<!everyone>", "@**all**")
    text = text.replace("<!channel>", "@**all**")
    text = text.replace("<!here>", "@**all**")
    return text


def convert_slack_formatting(text: str) -> str:
    text = convert_markdown_syntax(text, SLACK_BOLD_REGEX, "**")
    text = convert_markdown_syntax(text, SLACK_STRIKETHROUGH_REGEX, "~~")
    text = convert_markdown_syntax(text, SLACK_ITALIC_REGEX, "*")
    return text


# Markdown mapping
def convert_to_zulip_markdown(
    text: str,
    users: list[ZerverFieldsT],
    added_channels: AddedChannelsT,
    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
) -> tuple[str, list[int], bool]:
    mentioned_users_id = []
    text = convert_slack_formatting(text)
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

    # Check and convert link format
    text, has_link = convert_link_format(text)
    # convert `<mailto:foo@foo.com>` to `mailto:foo@foo.com`
    text, has_mailto_link = convert_mailto_format(text)

    message_has_link = has_link or has_mailto_link

    return text, mentioned_users_id, message_has_link


def render_block(block: WildValue) -> str:
    # https://api.slack.com/reference/block-kit/blocks
    block_type = block["type"].tame(
        check_string_in(["actions", "context", "divider", "header", "image", "input", "section"])
    )
    if block_type == "actions":
        # Unhandled
        return ""
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
                pieces.append(element.tame(check_text_block())["text"])
        return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")
    elif block_type == "divider":
        return "----"
    elif block_type == "header":
        return "## " + block["text"].tame(check_text_block(plain_text_only=True))["text"]
    elif block_type == "image":
        image_url = block["image_url"].tame(check_url)
        alt_text = block["alt_text"].tame(check_string)
        if "title" in block:
            alt_text = block["title"].tame(check_text_block(plain_text_only=True))["text"]
        return f"[{alt_text}]({image_url})"
    elif block_type == "input":
        # Unhandled
        pass
    elif block_type == "section":
        pieces = []
        if "text" in block:
            pieces.append(block["text"].tame(check_text_block())["text"])

        if "accessory" in block:
            pieces.append(render_block_element(block["accessory"]))

        if "fields" in block:
            fields = block["fields"].tame(check_list(check_text_block()))
            if len(fields) == 1:
                # Special-case a single field to display a bit more
                # nicely, without extraneous borders and limitations
                # on its contents.
                pieces.append(fields[0]["text"])
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

        return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")

    return ""


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
        image_url = element["image_url"].tame(check_url)
        alt_text = element["alt_text"].tame(check_string)
        return f"[{alt_text}]({image_url})"
    else:
        # Unsupported
        return ""


def render_attachment(attachment: WildValue) -> str:
    # https://api.slack.com/reference/messaging/attachments
    # Slack recommends the usage of "blocks" even within attachments; the
    # rest of the fields we handle here are legacy fields. These fields are
    # optional and may contain null values.
    pieces = []
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
        pieces.append(attachment["text"].tame(check_string))
    if "fields" in attachment:
        fields = []
        for field in attachment["fields"]:
            if "title" in field and "value" in field and field["title"] and field["value"]:
                title = field["title"].tame(check_string)
                value = field["value"].tame(check_string)
                fields.append(f"*{title}*: {value}")
            elif field.get("title"):
                title = field["title"].tame(check_string)
                fields.append(f"*{title}*")
            elif field.get("value"):
                value = field["value"].tame(check_string)
                fields.append(f"{value}")
        pieces.append("\n".join(fields))
    if attachment.get("blocks"):
        pieces += map(render_block, attachment["blocks"])
    if attachment.get("image_url"):
        pieces.append("[]({})".format(attachment["image_url"].tame(check_url)))
    if attachment.get("footer"):
        pieces.append(attachment["footer"].tame(check_string))
    if attachment.get("ts"):
        time = attachment["ts"].tame(check_int)
        pieces.append(f"<time:{time}>")

    return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")
