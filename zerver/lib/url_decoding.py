# See the Zulip URL spec at https://zulip.com/api/zulip-urls

import re
from collections.abc import Sequence
from datetime import date
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.narrow_helpers import (
    NarrowTerm,
    supported_channels_operands,
    supported_has_operands,
    supported_in_operands,
    supported_is_operands,
)
from zerver.lib.topic import DB_TOPIC_NAME


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


# JavaScript's `Number.MAX_SAFE_INTEGER`.
MAX_SAFE_INTEGER = 2**53 - 1


def is_safe_integer(operand: str | int | list[int]) -> bool:
    # Matches the web app's `Number.isSafeInteger(Number(operand))`,
    # except that strings must be plain decimal digits.
    if isinstance(operand, str):
        if not (operand.isascii() and operand.isdigit()):
            return False
        # Checking the length first keeps `int()` from raising on
        # strings longer than Python's 4300-digit conversion limit.
        digits = operand.lstrip("0")
        return len(digits) <= len(str(MAX_SAFE_INTEGER)) and int(digits or "0") <= MAX_SAFE_INTEGER
    if isinstance(operand, int):
        return abs(operand) <= MAX_SAFE_INTEGER
    return False


def is_valid_date(operand: str | int | list[int]) -> bool:
    if not isinstance(operand, str):
        return False
    try:
        parsed_date = date.fromisoformat(operand)
    except ValueError:
        return False
    # The date must strictly follow the YYYY-MM-DD format, to prevent
    # allowing dates like `2026-1-1` which cause all sorts of edge cases.
    if parsed_date.isoformat() != operand:
        return False
    # 1970 is the year of the unix epoch; anything earlier
    # predates timestamps we'd ever have messages for.
    return 1970 <= parsed_date.year <= timezone_now().year


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
    """Python copy of a subset of the web app's `Filter` class in
    `web/src/filter.ts`. Each method behaves like its web app
    counterpart, except that:

    - Operands have the types `parse_narrow_url` returns, which differ
      from the web app's for some operators (e.g., channel IDs are
      ints, not strings).
    - The server has no client-side user or channel data, so
      `is_valid_canonical_term` doesn't check that referenced users
      and channels exist.
    """

    def __init__(self, terms: Sequence[NarrowTerm]) -> None:
        self.setup_filter(terms)

    @staticmethod
    def canonicalize_term(term: NarrowTerm) -> NarrowTerm:
        operator = canonicalize_operator_synonyms(term.operator)
        operand = term.operand
        match operator:
            case "is":
                # "is:private" was renamed to "is:dm"
                if operand == "private":
                    operand = "dm"
            case "has":
                # images -> image, etc.
                if isinstance(operand, str):
                    operand = operand.removesuffix("s")
            case "channel" | "topic" | "sender" | "mentions" | "dm" | "dm-including" | "date":
                pass
            case "search":
                # The mac app automatically substitutes regular quotes with curly
                # quotes when typing in the search bar.  Curly quotes don't trigger our
                # phrase search behavior, however.  So, we replace all instances of
                # curly quotes with regular quotes when doing a search.  This is
                # unlikely to cause any problems and is probably what the user wants.
                if isinstance(operand, str):
                    operand = re.sub(r"[\u201C\u201D]", '"', operand)
            case "channels" | "id" | "in" | "near" | "with" | "":
                if isinstance(operand, str):
                    operand = operand.lower()
            case _:
                # The web app throws on unknown operators here. We pass
                # them through, and `is_valid_canonical_term` rejects them.
                pass

        return NarrowTerm(operator, operand, term.negated)

    @staticmethod
    def is_valid_canonical_term(term: NarrowTerm) -> bool:
        operand = term.operand
        match term.operator:
            case "has":
                return operand in supported_has_operands
            case "is":
                return operand in supported_is_operands
            case "in":
                return operand in supported_in_operands
            case "id" | "near" | "with":
                # Negating these doesn't have a useful meaning,
                # so we reject it (matching `date` below).
                if term.negated:
                    return False
                return is_safe_integer(operand)
            case "channel":
                return isinstance(operand, int) and operand > 0
            case "channels":
                return operand in supported_channels_operands
            case "topic":
                return True
            case "sender" | "mentions":
                return isinstance(operand, int) and operand > 0
            case "dm" | "dm-including":
                return isinstance(operand, list) and all(user_id > 0 for user_id in operand)
            case "search" | "":
                return True
            case "date":
                if term.negated:
                    return False
                return is_valid_date(operand)
            case _:
                return False

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
    def fix_terms(terms: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        terms = Filter._canonicalize_terms(terms)
        terms = Filter._fix_redundant_is_private(terms)
        return terms

    def setup_filter(self, terms: Sequence[NarrowTerm]) -> None:
        self._terms = self.fix_terms(terms)

    def terms(self) -> list[NarrowTerm]:
        return self._terms

    def terms_with_operator(self, operator: str) -> list[NarrowTerm]:
        return [term for term in self.terms() if term.operator == operator and not term.negated]
