
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

class RequestedPrunedEventsError(JsonableError):
    code = ErrorCode.REQUESTED_PRUNED_EVENTS
    data_fields = ['last_event_id']

    def __init__(self, last_event_id: int) -> None:
        self.last_event_id = last_event_id  # type: int

    @staticmethod
    def msg_format() -> str:
        return _("Events older than %(last_event_id)s have already been pruned!")
