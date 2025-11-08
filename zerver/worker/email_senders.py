# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
from zerver.worker.base import assign_queue
from zerver.worker.email_senders_base import EmailSendingWorker


@assign_queue("email_senders")
class ImmediateEmailSenderWorker(EmailSendingWorker):
    pass
