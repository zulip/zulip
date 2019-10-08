
from django.utils.translation import ugettext as _

from zerver.lib.exceptions import ErrorCode, JsonableError

class BadEventQueueIdError(JsonableError):
    code = ErrorCode.BAD_EVENT_QUEUE_ID
    data_fields = ['queue_id']

    def __init__(self, queue_id: str) -> None:
        self.queue_id = queue_id  # type: str

    @staticmethod
    def msg_format() -> str:
        return _("Bad event queue id: {queue_id}")
