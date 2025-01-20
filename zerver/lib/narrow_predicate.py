from collections.abc import Collection
from typing import Any, Protocol

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.narrow_helpers import NeverNegatedNarrowTerm
from zerver.lib.topic import RESOLVED_TOPIC_PREFIX, get_topic_from_message_info

# "stream" is a legacy alias for "channel"
channel_operators: list[str] = ["channel", "stream"]
# "streams" is a legacy alias for "channels"
channels_operators: list[str] = ["channels", "streams"]


def check_narrow_for_events(narrow: Collection[NeverNegatedNarrowTerm]) -> None:
    supported_operators = [*channel_operators, "topic", "sender", "is"]
    unsupported_is_operands = ["followed"]
    for narrow_term in narrow:
        operator = narrow_term.operator
        if operator not in supported_operators:
            raise JsonableError(_("Operator {operator} not supported.").format(operator=operator))
        if operator == "is" and narrow_term.operand in unsupported_is_operands:
            raise JsonableError(
                _("Operand {operand} not supported.").format(operand=narrow_term.operand)
            )


class NarrowPredicate(Protocol):
    def __call__(self, *, message: dict[str, Any], flags: list[str]) -> bool: ...


def build_narrow_predicate(
    narrow: Collection[NeverNegatedNarrowTerm],
) -> NarrowPredicate:
    """Changes to this function should come with corresponding changes to
    NarrowLibraryTest."""
    check_narrow_for_events(narrow)

    def narrow_predicate(*, message: dict[str, Any], flags: list[str]) -> bool:
        def satisfies_operator(*, operator: str, operand: str) -> bool:
            if operator in channel_operators:
                if message["type"] != "stream":
                    return False
                if operand.lower() != message["display_recipient"].lower():
                    return False
            elif operator == "topic":
                if message["type"] != "stream":
                    return False
                topic_name = get_topic_from_message_info(message)
                if operand.lower() != topic_name.lower():
                    return False
            elif operator == "sender":
                if operand.lower() != message["sender_email"].lower():
                    return False
            elif operator == "is" and operand in ["dm", "private"]:
                # "is:private" is a legacy alias for "is:dm"
                if message["type"] != "private":
                    return False
            elif operator == "is" and operand in ["starred"]:
                if operand not in flags:
                    return False
            elif operator == "is" and operand == "unread":
                if "read" in flags:
                    return False
            elif operator == "is" and operand in ["alerted", "mentioned"]:
                if "mentioned" not in flags:
                    return False
            elif operator == "is" and operand == "resolved":
                if message["type"] != "stream":
                    return False
                topic_name = get_topic_from_message_info(message)
                if not topic_name.startswith(RESOLVED_TOPIC_PREFIX):
                    return False
            return True

        for narrow_term in narrow:
            # TODO: Eventually handle negated narrow terms.
            if not satisfies_operator(operator=narrow_term.operator, operand=narrow_term.operand):
                return False

        return True

    return narrow_predicate
