import unicodedata
from typing import Optional

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models import Stream

# There are 66 Unicode non-characters; see
# https://www.unicode.org/faq/private_use.html#nonchar4
unicode_non_chars = set(
    chr(x)
    for x in list(range(0xFDD0, 0xFDF0))  # FDD0 through FDEF, inclusive
    + list(range(0xFFFE, 0x110000, 0x10000))  # 0xFFFE, 0x1FFFE, ... 0x10FFFE inclusive
    + list(range(0xFFFF, 0x110000, 0x10000))  # 0xFFFF, 0x1FFFF, ... 0x10FFFF inclusive
)


def check_string_is_printable(var: str) -> Optional[int]:
    # Return position (1-indexed!) of the character which is not
    # printable, None if no such character is present.
    for i, char in enumerate(var):
        unicode_character = unicodedata.category(char)
        if (unicode_character in ["Cc", "Cs"]) or char in unicode_non_chars:
            return i + 1
    return None


def check_stream_name(stream_name: str) -> None:
    if stream_name.strip() == "":
        raise JsonableError(_("Stream name can't be empty!"))

    if len(stream_name) > Stream.MAX_NAME_LENGTH:
        raise JsonableError(
            _("Stream name too long (limit: {} characters).").format(Stream.MAX_NAME_LENGTH)
        )
    for i in stream_name:
        if ord(i) == 0:
            raise JsonableError(
                _("Stream name '{}' contains NULL (0x00) characters.").format(stream_name)
            )


def check_stream_topic(topic: str) -> None:
    if topic.strip() == "":
        raise JsonableError(_("Topic can't be empty!"))

    invalid_character_pos = check_string_is_printable(topic)
    if invalid_character_pos is not None:
        raise JsonableError(
            _("Invalid character in topic, at position {}!").format(invalid_character_pos)
        )
