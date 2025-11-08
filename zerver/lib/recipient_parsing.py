from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError


def extract_stream_id(req_to: int | list[int]) -> int:
    # Recipient should only be a single stream ID.
    if isinstance(req_to, list):
        raise JsonableError(_("Invalid data type for channel ID"))
    return req_to


def extract_direct_message_recipient_ids(req_to: int | list[int]) -> list[int]:
    if not isinstance(req_to, list):
        raise JsonableError(_("Invalid data type for recipients"))

    return list(set(req_to))
