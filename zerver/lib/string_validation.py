import unicodedata
from typing import Optional

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models import Stream

# There are 66 Unicode non-characters; see
# https://www.unicode.org/faq/private_use.html#nonchar4
unicode_non_chars = {
    chr(x)
    for r in [
        range(0xFDD0, 0xFDF0),  # FDD0 through FDEF, inclusive
        range(0xFFFE, 0x110000, 0x10000),  # 0xFFFE, 0x1FFFE, ... 0x10FFFE inclusive
        range(0xFFFF, 0x110000, 0x10000),  # 0xFFFF, 0x1FFFF, ... 0x10FFFF inclusive
    ]
    for x in r
}


def is_character_printable(char: str) -> bool:
    unicode_category = unicodedata.category(char)
    if (unicode_category in ["Cc", "Cs"]) or char in unicode_non_chars:
        return False

    return True


def check_string_is_printable(var: str) -> Optional[int]:
    # Return position (1-indexed!) of the character which is not
    # printable, None if no such character is present.
    for i, char in enumerate(var):
        if not is_character_printable(char):
            return i + 1
    return None


def check_stream_name(stream_name: str) -> None:
    if stream_name.strip() == "":
        raise JsonableError(_("Channel name can't be empty."))

    if len(stream_name) > Stream.MAX_NAME_LENGTH:
        raise JsonableError(
            _("Channel name too long (limit: {max_length} characters).").format(
                max_length=Stream.MAX_NAME_LENGTH
            )
        )

    invalid_character_pos = check_string_is_printable(stream_name)
    if invalid_character_pos is not None:
        raise JsonableError(
            _("Invalid character in channel name, at position {position}.").format(
                position=invalid_character_pos
            )
        )


def check_stream_topic(topic_name: str) -> None:
    if topic_name.strip() == "":
        raise JsonableError(_("Topic can't be empty!"))

    invalid_character_pos = check_string_is_printable(topic_name)
    if invalid_character_pos is not None:
        raise JsonableError(
            _("Invalid character in topic, at position {position}!").format(
                position=invalid_character_pos
            )
        )
