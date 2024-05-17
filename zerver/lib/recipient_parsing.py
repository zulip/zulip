from typing import List

import orjson
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError


def extract_stream_id(req_to: str) -> int:
    # Recipient should only be a single stream ID.
    try:
        stream_id = int(req_to)
    except ValueError:
        raise JsonableError(_("Invalid data type for channel ID"))
    return stream_id


def extract_direct_message_recipient_ids(req_to: str) -> List[int]:
    try:
        user_ids = orjson.loads(req_to)
    except orjson.JSONDecodeError:
        user_ids = req_to

    if not isinstance(user_ids, list):
        raise JsonableError(_("Invalid data type for recipients"))

    for user_id in user_ids:
        if not isinstance(user_id, int):
            raise JsonableError(_("Recipient list may only contain user IDs"))

    return list(set(user_ids))
