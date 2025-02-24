# See the Zulip URL spec at https://zulip.com/api/zulip-urls

import re
from collections.abc import Sequence
from urllib.parse import unquote, urlsplit

from django.conf import settings

from zerver.lib.exceptions import BadNarrowOperatorError
from zerver.lib.narrow_helpers import (
    NarrowTerm,
    supported_channels_operands,
    supported_has_operands,
    supported_in_operands,
    supported_is_operands,
)
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.models.messages import Message


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

OPERATOR_SYNONYMS = {
    **CHANNEL_SYNONYMS,
    # "pm-with:" was renamed to "dm:"
    "pm-with": "dm",
    # "group-pm-with:" was replaced with "dm-including:"
    "group-pm-with": "dm-including",
    "from": "sender",
    DB_TOPIC_NAME: "topic",
}


def canonicalize_operator_synonyms(text: str) -> str:
    text = text.lower()
    if text in OPERATOR_SYNONYMS.values():
        return text
    if text in OPERATOR_SYNONYMS:
        return OPERATOR_SYNONYMS[text]
    return text


def parse_recipient_slug(slug: str) -> tuple[int | list[int], str] | None:
    """
    Parses operands formatted in slug containing object ID or IDs.
    Typical of "channel" or private message operands.

    Doesn't parse the legacy pre-2018 stream slug format, which would
    require using data for what channels exist for a proper parse.
        e.g. "stream-name"

    Returns a tuple of parsed ids and the recipient info (channel name,
    DM'ed users name, etc) or only `None` if the operand is invalid.
        e.g.
        - "12,13,14-group" -> ([12, 13, 14], "group")
        - "89-Markl" -> (89, "Markl")
        - "stream-name" -> None
    """
    try:
        ids_string, suffix = slug.split("-", maxsplit=1)
        ids = [int(id) for id in ids_string.split(",")]
        return (ids if len(ids) > 1 else ids[0], suffix)
    except ValueError:
        # We expect this to happen both for invalid URLs and legacy
        # pre-2018 channel link URLs that don't have a channel ID in
        # the slug.
        return None


def is_ascii_digits(text: str) -> bool:
    return text.isascii() and text.isdigit()


def decode_hash_component(string: str) -> str:
    # This matches the web app's implementation of decodeHashComponent.
    return unquote(string.replace(".", "%"))


def decode_narrow_operand(operator: str, operand: str) -> str | int | list[int]:
    # These have the similar slug formatting for their operands which
    # contain object ID(s).
    if operator in ["dm-including", "dm", "mentions", "sender", "channel"]:
        result = parse_recipient_slug(operand)
        return result[0] if isinstance(result, tuple) else ""

    if operator == "near":
        return int(operand) if operand.isdigit() else ""

    operand = decode_hash_component(operand).strip()

    return operand


def parse_narrow_url(
    narrow_url: str,
) -> list[NarrowTerm] | None:
    """This server implementation is intended to match the algorithm
    for the web app's `parse_narrow` in `hash_util.ts`. It largely
    behaves the same way and has the same purpose: to parse a narrow
    URL into a list of `NarrowTerm`.

    The key difference from the web app implementation is that this
    does not validate the referenced objects (users and channels).
    """
    split_result = urlsplit(narrow_url)
    fragment = split_result.fragment
    fragment_parts = fragment.split("/")

    terms: list[NarrowTerm] = []

    for i in range(1, len(fragment_parts), 2):
        raw_operator = decode_hash_component(fragment_parts[i]).strip()

        if not raw_operator:
            return None

        negated = False
        if raw_operator.startswith("-"):
            negated = True
            raw_operator = raw_operator[1:]
        operator = canonicalize_operator_synonyms(raw_operator)

        try:
            raw_operand = fragment_parts[i + 1]
        except IndexError:
            raw_operand = ""
        operand = decode_narrow_operand(operator, raw_operand)

        if operand == "" and operator != "topic":
            # The empty string is a valid topic (realm_empty_topic_display_name).
            #
            # Other empty string operands are invalid.
            return None

        terms.append(NarrowTerm(operator, operand, negated))
    return terms


class Filter:
    """Canonicalizes a list of narrow terms. Prefer passing it the
    terms returned by `parse_narrow_url`.
    """

    def __init__(self, terms: Sequence[NarrowTerm]) -> None:
        self._setup_filter(terms)

    @staticmethod
    def reformat_channel_operand(operand: str | int) -> str | int:
        match operand:
            case int():
                return operand
            case str():
                if operand.strip() == "":
                    raise BadNarrowOperatorError("Invalid 'channel' operand")
                if is_ascii_digits(operand):
                    return int(operand)
                if result := parse_recipient_slug(operand.lower()):
                    channel_id = result[0]
                    if not isinstance(channel_id, int):
                        raise BadNarrowOperatorError("Invalid 'channel' operand")
                    return channel_id
                # if it's not a channel ID nor encoded channel slug, it's
                # probably a channel name.
                return operand

    @staticmethod
    def reformat_dm_operand(operand: object) -> str | list[int]:
        match operand:
            case int():
                return [operand]
            case str():
                if is_ascii_digits(operand):
                    return [int(operand)]
                if operand.strip() == "":
                    raise BadNarrowOperatorError("Invalid user ID")
                return operand.lower()
            case list():
                if operand == []:
                    raise BadNarrowOperatorError("Invalid user ID")
                user_ids: list[int] = []
                for user_id in operand:
                    if not isinstance(user_id, int):
                        raise BadNarrowOperatorError("Invalid user ID")
                    user_ids.append(user_id)
                return user_ids
            case _:
                raise BadNarrowOperatorError("Invalid user ID")

    @staticmethod
    def canonicalize_term(term: NarrowTerm) -> NarrowTerm:
        operator = canonicalize_operator_synonyms(term.operator)
        operand = term.operand
        match operator:
            case "channel" if isinstance(operand, str | int):
                operand = Filter.reformat_channel_operand(operand)

            case "channels" if isinstance(operand, str):
                operand = operand.lower()
                if operand not in supported_channels_operands:
                    raise BadNarrowOperatorError(f"unknown '{operator}' operand {operand!s}")

            case "dm":
                operand = Filter.reformat_dm_operand(operand)

            case "dm-including" | "mentions" | "sender" if isinstance(operand, int):
                if operand < 0:
                    raise BadNarrowOperatorError("Invalid user ID")

            case "dm-including" | "mentions" | "sender" if isinstance(operand, str):
                if is_ascii_digits(operand):
                    operand = int(operand)
                elif operand.strip() == "":
                    raise BadNarrowOperatorError("Invalid user ID")
                else:
                    operand = operand.lower()

            case "has":
                # images -> image, etc.
                operand = re.sub(r"s$", "", str(operand))
                if operand not in supported_has_operands:
                    raise BadNarrowOperatorError(f"unknown '{operator}' operand {operand!s}")

            case "id" | "near" | "with" if isinstance(operand, int | str):
                if (
                    not is_ascii_digits(str(operand))
                    or int(operand) > Message.MAX_POSSIBLE_MESSAGE_ID
                ):
                    raise BadNarrowOperatorError("Invalid message ID")
                operand = int(operand)

            case "in" if isinstance(operand, str):
                operand = operand.lower()
                if operand not in supported_in_operands:
                    raise BadNarrowOperatorError(f"unknown '{operator}' operand {operand!s}")

            case "is" if isinstance(operand, str):
                operand = operand.lower()
                if operand == "private":
                    # "is:private" was renamed to "is:dm"
                    operand = "dm"
                if operand not in supported_is_operands:
                    raise BadNarrowOperatorError(f"unknown '{operator}' operand {operand!s}")

            case "search":
                # The mac app automatically substitutes regular quotes with curly
                # quotes when typing in the search bar.  Curly quotes don't trigger our
                # phrase search behavior, however.  So, we replace all instances of
                # curly quotes with regular quotes when doing a search.  This is
                # unlikely to cause any problems and is probably what the user wants.
                operand = re.sub(r"[\u201C\u201D]", '"', str(operand).lower())

            case "topic" if isinstance(operand, str):
                pass

            case _:
                raise BadNarrowOperatorError(f"unknown '{operator}' operand {operand!s}")

        return NarrowTerm(operator, operand, term.negated)

    @staticmethod
    def term_type(term: NarrowTerm) -> str:
        result = "not-" if term.negated else ""
        result += term.operator

        if term.operator in ["is", "has", "in", "channels"]:
            result += "-" + str(term.operand)

        return result

    @staticmethod
    def _canonicalize_terms(terms_mixed_case: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        return [Filter.canonicalize_term(term) for term in terms_mixed_case]

    @staticmethod
    def _fix_redundant_is_private(terms: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        # Every DM is a DM, so drop `is:dm` if on a DM conversation.
        if not any(Filter.term_type(term) == "dm" for term in terms):
            return list(terms)
        return [term for term in terms if Filter.term_type(term) != "is-dm"]

    @staticmethod
    def _fix_terms(terms: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        terms = Filter._canonicalize_terms(terms)
        terms = Filter._fix_redundant_is_private(terms)
        return terms

    def _setup_filter(self, terms: Sequence[NarrowTerm]) -> None:
        self._terms = self._fix_terms(terms)

    def terms(self) -> list[NarrowTerm]:
        return self._terms
