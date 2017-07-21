from __future__ import absolute_import
from typing import Text

from django.utils.translation import ugettext as _

from zerver.lib.exceptions import JsonableError, ErrorCode

class BadEventQueueIdError(JsonableError):
    code = ErrorCode.BAD_EVENT_QUEUE_ID
    data_fields = ['queue_id']

    def __init__(self, queue_id):
        # type: (Text) -> None
        self.queue_id = queue_id  # type: Text

    @staticmethod
    def msg_format():
        # type: () -> Text
        return _("Bad event queue id: {queue_id}")
