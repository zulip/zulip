import re
from collections.abc import Iterable, Sequence
from functools import cmp_to_key
from typing import Any
from urllib.parse import unquote, urlsplit

from django.conf import settings

from zerver.lib.narrow import BadNarrowOperatorError, InvalidOperatorCombinationError
from zerver.lib.narrow_helpers import NarrowTerm, NarrowTermOperandT
from zerver.lib.streams import get_stream_by_narrow_operand_access_unchecked
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.lib.url_encoding import encode_stream, hash_util_encode
from zerver.models.messages import Message
from zerver.models.realms import Realm
from zerver.models.streams import Stream


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


def decode_hash_component(string: str) -> str:
    # This matches the web app's implementation of decodeHashComponent.
    return unquote(string.replace(".", "%"))


def decode_narrow_operand(operator: str, operand: str) -> str | int | list[int]:
    # These have the similar slug formatting for their operands which
    # contain object ID(s).
    if operator in ["dm-including", "dm", "sender", "channel"]:
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

        if operand == "" and operator not in ["topic"]:
            # The empty string is a valid topic (realm_empty_topic_display_name).
            #
            # Other empty string operands are invalid.
            return None

        terms.append(NarrowTerm(operator, operand, negated))
    return terms


NARROW_FRAGMENT_BASE = "#narrow/"


class Filter:
    def __init__(self, terms: Sequence[NarrowTerm], realm: Realm) -> None:
        self._terms: list[NarrowTerm] = list(terms)
        self._realm: Realm = realm
        self._sorted_term_types: list[str] | None = None
        self._setup_filter(terms)

    @staticmethod
    def reformat_channel_operand(operand: str | int) -> str | int:
        match operand:
            case int():
                return operand
            case str():
                if operand.strip() == "":
                    raise BadNarrowOperatorError("Invalid 'channel' operand")
                if operand.isdigit():
                    return int(operand)
                if result := parse_recipient_slug(operand.lower()):
                    assert isinstance(result[0], int)
                    return result[0]
                # if it's not a channel ID nor encoded channel slug, it's
                # probably a channel name.
                return operand

    @staticmethod
    def reformat_dm_operand(operand: str | int | Iterable[Any]) -> str | list[int]:
        match operand:
            case int():
                return [operand]
            case str():
                if operand.isdigit():
                    return [int(operand)]
                if operand.strip() == "":
                    raise BadNarrowOperatorError("Invalid user ID")
                return operand.lower()
            case Iterable():
                try:
                    user_ids = [int(id) for id in operand]
                    assert user_ids != []
                    return user_ids
                except (ValueError, AssertionError):
                    raise BadNarrowOperatorError("Invalid user ID")

    @staticmethod
    def canonicalize_term(term: NarrowTerm) -> NarrowTerm:
        operator = canonicalize_operator_synonyms(term.operator)
        operand = term.operand
        match operator:
            case "channel" if isinstance(operand, str | int):
                operand = Filter.reformat_channel_operand(operand)

            case "channels" if str(operand) in {"public", "web-public"}:
                pass

            case "dm":
                operand = Filter.reformat_dm_operand(operand)

            case "dm-including" | "sender" if isinstance(operand, str | int):
                operand = int(operand) if str(operand).isdigit() else str(operand).lower()
                if str(operand).strip() == "":
                    raise BadNarrowOperatorError("Invalid user ID")
            case "has":
                # images -> image, etc.
                operand = re.sub(r"s$", "", str(operand))
                if operand not in {"attachment", "image", "link", "reaction"}:
                    raise BadNarrowOperatorError(f"unknown '{operator}' operand {operand!s}")

            case "id" | "near" | "with" if isinstance(operand, int | str):
                if not str(operand).isdigit() or int(operand) > Message.MAX_POSSIBLE_MESSAGE_ID:
                    raise BadNarrowOperatorError("Invalid message ID")
                operand = int(operand)

            case "is" if isinstance(operand, str):
                operand = operand.lower()
                if operand == "private":
                    # "is:private" was renamed to "is:dm"
                    operand = "dm"
                if operand not in {
                    "dm",
                    "starred",
                    "unread",
                    "mentioned",
                    "alerted",
                    "resolved",
                    "followed",
                }:
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
    def sorted_term_types(term_types: list[str]) -> list[str]:
        # Keep this algorithm in sync with the the static method of the same name in
        # `filter.Filter` in the frontend.
        levels: Sequence[str] = [
            "in",
            "channels-public",
            "channel",
            "topic",
            "dm",
            "dm-including",
            "with",
            "sender",
            "near",
            "id",
            "is-alerted",
            "is-mentioned",
            "is-dm",
            "is-starred",
            "is-unread",
            "is-resolved",
            "is-followed",
            "has-link",
            "has-image",
            "has-attachment",
            "search",
        ]

        def level(term_type: str) -> int:
            try:
                return levels.index(term_type)
            except ValueError:
                return 999

        def compare(a: str, b: str) -> int:
            return level(a) - level(b)

        return sorted(term_types, key=cmp_to_key(compare))

    def _build_sorted_term_types(self) -> list[str]:
        term_types = [Filter.term_type(term) for term in self._terms]
        self._sorted_term_types = Filter.sorted_term_types(term_types)
        return self._sorted_term_types

    def _check_either_channel_or_dm_narrow(self) -> bool:
        """
        Asserts that the given terms narrow to a channel OR
        direct message.

        Returns `True` if channel narrow or `False` if direct
        narrow.

        Raises `InvalidOperatorCombinationError` if the terms
        narrow down to both or neither.
        """
        dm_operators = {"dm", "dm-including", "is-dm"}
        channel_operators = {"channel", "channels-public", "topic"}

        term_types = set(self._build_sorted_term_types())

        has_dm = not term_types.isdisjoint(dm_operators)
        has_channel = not term_types.isdisjoint(channel_operators)

        if has_dm and has_channel:
            raise InvalidOperatorCombinationError(
                "No message can be both a channel message and direct message"
            )

        if not has_dm and not has_channel:
            raise InvalidOperatorCombinationError("Not a channel message nor a direct message")

        return has_channel

    def _canonicalize_terms(self, terms_mixed_case: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        return [Filter.canonicalize_term(term) for term in terms_mixed_case]

    def _fix_redundant_is_private(self, terms: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        if not any(Filter.term_type(term) == "dm" for term in terms):
            return list(terms)
        return [term for term in terms if Filter.term_type(term) != "is-dm"]

    def _fix_terms(self, terms: Sequence[NarrowTerm]) -> list[NarrowTerm]:
        terms = self._canonicalize_terms(terms)
        terms = self._fix_redundant_is_private(terms)
        return terms

    def _setup_filter(self, terms: Sequence[NarrowTerm]) -> None:
        self._terms = self._fix_terms(terms)

    def terms(self) -> list[NarrowTerm]:
        return self._terms

    def operands(self, operator: str) -> list[NarrowTermOperandT]:
        return [
            term.operand for term in self.terms() if term.operator == operator and not term.negated
        ]

    def get_terms(self, operator: str) -> list[NarrowTerm]:
        return [term for term in self.terms() if term.operator == operator]

    def update_term(self, existing_term: NarrowTerm, new_term: NarrowTerm) -> None:
        current_terms = self.terms()
        try:
            term_index = current_terms.index(existing_term)
        except ValueError:
            raise AssertionError("Invalid term to update")
        new_terms = self.terms()
        new_terms[term_index] = new_term
        self._setup_filter(new_terms)

    def generate_channel_url(self) -> str:
        self._check_either_channel_or_dm_narrow()
        recipients = self.operands("channel")
        if not len(recipients) == 1:
            raise InvalidOperatorCombinationError("Requires exactly one 'channel' operand")
        channel_id_or_name = recipients[0]
        assert isinstance(channel_id_or_name, str | int)
        try:
            channel = get_stream_by_narrow_operand_access_unchecked(channel_id_or_name, self._realm)
        except Stream.DoesNotExist:
            raise BadNarrowOperatorError("unknown channel " + str(channel_id_or_name))

        return NARROW_FRAGMENT_BASE + f"channel/{encode_stream(channel.id, channel.name)}"

    def generate_topic_url(self) -> str:
        channel_link = self.generate_channel_url()
        topics = self.operands("topic")
        if not len(topics) == 1:
            raise InvalidOperatorCombinationError("Requires exactly one 'topic' operand")
        topic_name = topics[0]
        assert isinstance(topic_name, str)
        return f"{channel_link}/topic/{hash_util_encode(topic_name)}"
