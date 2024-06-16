# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import copy
import logging
import socket
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from django.core.mail.backends.base import BaseEmailBackend
from typing_extensions import override

from zerver.lib.queue import retry_event
from zerver.lib.send_email import (
    EmailNotDeliveredError,
    handle_send_email_format_changes,
    initialize_connection,
    send_email,
)
from zerver.models import Realm
from zerver.worker.base import ConcreteQueueWorker, LoopQueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


# If you change the function on which this decorator is used be careful that the new
# function doesn't delete the "failed_tries" attribute of "data" which is needed for
# "retry_event" to work correctly; see EmailSendingWorker for an example with deepcopy.
def retry_send_email_failures(
    func: Callable[[ConcreteQueueWorker, Dict[str, Any]], None],
) -> Callable[[ConcreteQueueWorker, Dict[str, Any]], None]:
    @wraps(func)
    def wrapper(worker: ConcreteQueueWorker, data: Dict[str, Any]) -> None:
        try:
            func(worker, data)
        except (socket.gaierror, TimeoutError, EmailNotDeliveredError) as e:
            error_class_name = type(e).__name__

            def on_failure(event: Dict[str, Any]) -> None:
                logging.exception(
                    "Event %r failed due to exception %s", event, error_class_name, stack_info=True
                )

            retry_event(worker.queue_name, data, on_failure)

    return wrapper


@assign_queue("email_senders")
class EmailSendingWorker(LoopQueueProcessingWorker):
    def __init__(
        self,
        threaded: bool = False,
        disable_timeout: bool = False,
        worker_num: Optional[int] = None,
    ) -> None:
        super().__init__(threaded, disable_timeout, worker_num)
        self.connection: Optional[BaseEmailBackend] = None

    @retry_send_email_failures
    def send_email(self, event: Dict[str, Any]) -> None:
        # Copy the event, so that we don't pass the `failed_tries'
        # data to send_email (which neither takes that
        # argument nor needs that data).
        copied_event = copy.deepcopy(event)
        if "failed_tries" in copied_event:
            del copied_event["failed_tries"]
        handle_send_email_format_changes(copied_event)
        if "realm_id" in copied_event:
            # "realm" does not serialize over the queue, so we send the realm_id
            copied_event["realm"] = Realm.objects.get(id=copied_event["realm_id"])
            del copied_event["realm_id"]
        self.connection = initialize_connection(self.connection)
        send_email(**copied_event, connection=self.connection)

    @override
    def consume_batch(self, events: List[Dict[str, Any]]) -> None:
        for event in events:
            self.send_email(event)

    @override
    def stop(self) -> None:
        try:
            if self.connection is not None:
                self.connection.close()
        finally:
            super().stop()
