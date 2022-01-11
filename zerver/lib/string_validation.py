import unicodedata
from typing import Optional

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models import Stream


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
        raise JsonableError(_("Topic can't be empty"))

    for character in topic:
        unicodeCategory = unicodedata.category(character)
        if unicodeCategory in ["Cc", "Cs", "Cn"]:
            raise JsonableError(_("Invalid characters in topic!"))
