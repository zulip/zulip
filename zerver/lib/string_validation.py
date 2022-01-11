from typing import Optional

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models import Stream


def check_stream_name(stream_name: str) -> None:
    if stream_name.strip() == "":
        raise JsonableError(_("Invalid stream name '{}'").format(stream_name))
    if len(stream_name) > Stream.MAX_NAME_LENGTH:
        raise JsonableError(
            _("Stream name too long (limit: {} characters).").format(Stream.MAX_NAME_LENGTH)
        )
    for i in stream_name:
        if ord(i) == 0:
            raise JsonableError(
                _("Stream name '{}' contains NULL (0x00) characters.").format(stream_name)
            )
