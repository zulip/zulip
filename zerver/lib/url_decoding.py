from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from django.conf import settings

from zerver.lib.narrow_helpers import NarrowTerm


@dataclass
class RecipientMetadata:
    id: list[int] | int
    suffix: str


def is_same_server_message_link(url: str) -> bool:
    split_result = urlsplit(url)
    hostname = split_result.hostname
    fragment = split_result.fragment

    if hostname not in {None, settings.EXTERNAL_HOST_WITHOUT_PORT}:
        return False

    # A message link always has category `narrow`, section `channel`
    # or `dm`, and ends with `/near/<message_id>`, where <message_id>
    # is a sequence of digits. The URL fragment of a message link has
    # at least 5 parts. e.g. '#narrow/dm/9,15-dm/near/43'
    fragment_parts = fragment.split("/")
    if len(fragment_parts) < 5:
        return False

    category = fragment_parts[0]
    section = fragment_parts[1]
    ends_with_near_message_id = fragment_parts[-2] == "near" and fragment_parts[-1].isdigit()

    return category == "narrow" and section in {"channel", "dm"} and ends_with_near_message_id


CHANNEL_SYNONYMS = {"stream": "channel", "streams": "channels"}


def canonicalize_channel_synonyms(text: str) -> str:
    text = text.lower()
    if text in CHANNEL_SYNONYMS.values():
        return text
    if text in CHANNEL_SYNONYMS:
        return CHANNEL_SYNONYMS[text]
    return text


def canonicalize_operator_synonyms(operand: str) -> str:
    operand = canonicalize_channel_synonyms(operand)

    return operand


def parse_recipient_slug(slug: str) -> RecipientMetadata | None:
    """
    Parses operands formatted in slug containing object ID or IDs.
    Typical of "channel" or private message operands.

    Doesn't parse the legacy stream slug.
        e.g. "stream-name"

    Returns the parsed ids and the recipient info (channel name,
    DM'ed users name, etc) or only `None` if the operand is invalid.
        e.g.
        - "12,13,14-group" -> {id: [12, 13, 14], suffix: "group"}
        - "89-Markl" -> {id: 89, suffix: "Markl"}
        - "stream-name" -> None
    """
    try:
        ids_string, suffix = slug.split("-", maxsplit=1)
        ids = [int(id) for id in ids_string.split(",")]
        return RecipientMetadata(ids if len(ids) > 1 else ids[0], suffix)
    except ValueError:
        # We primarily expect this to catch the legacy stream
        # slug or broken URLs.
        return None


def hash_util_decode(string: str) -> str:
    # Do the same decoding operation as shared internal_url.decodeHashComponent
    # on the frontend.
    return unquote(string.replace(".", "%"))


def decode_narrow_operand(operator: str, operand: str) -> Any:
    # These have the similar slug formatting for their operands which contains
    # object ID(s).
    if operator in ["group-pm-with", "dm-including", "dm", "sender", "pm-with", "channel"]:
        result = parse_recipient_slug(operand)
        return result.id if result is not None else ""

    if operator == "near":
        return int(operand) if operand.isdigit() else ""

    operand = hash_util_decode(operand).strip()

    return operand


def parse_narrow_url(
    narrow_url: str,
) -> list[NarrowTerm] | None:
    """
    This is the web app version of `parse_narrow` in `hash_util.ts`. It
    largely behaves the same way and has the same purpose: to parse a
    narrow URL into a list of `NarrowTerm`.

    The differences, other than some algorithms being done in a "Pythonic"
    way, are:

        - This doesn't convert a user-id-slug into a list of user emails;
        it will instead parse it into a list of their IDs.

        - Operands can be an actual list or int instead of a list or int as
        a string (e.g., "12,14,15" or "93").

        - Unlike the frontend counterpart, this doesn't validate the referenced
        objects (users and channels).
    """
    split_result = urlsplit(narrow_url)
    fragment = split_result.fragment
    fragment_parts = fragment.split("/")

    terms: list[NarrowTerm] = []

    for i in range(1, len(fragment_parts), 2):
        operator = hash_util_decode(fragment_parts[i]).strip()

        if not operator:
            return None

        try:
            raw_operand = fragment_parts[i + 1]
        except IndexError:
            raw_operand = ""

        negated = False
        if operator.startswith("-"):
            negated = True
            operator = operator[1:]

        operator = canonicalize_operator_synonyms(operator)
        operand = decode_narrow_operand(operator, raw_operand)

        if operator not in ["topic", "channel"] and not operand:
            # We allow the empty string as a topic name because of #32963.
            # For empty channel strings, frontend can handle this by showing
            # "Invalid stream" in navbar.
            # Any other operand being empty string is invalid.
            return None

        terms.append(NarrowTerm(operator, operand, negated))
    return terms
