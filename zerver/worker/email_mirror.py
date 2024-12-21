# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import base64
import email.parser
import email.policy
import logging
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any

from typing_extensions import override

from zerver.lib.email_mirror import (
    decode_stream_email_address,
    is_missed_message_address,
    rate_limit_mirror_by_realm,
)
from zerver.lib.email_mirror import process_message as mirror_email
from zerver.lib.exceptions import RateLimitedError
from zerver.worker.base import QueueProcessingWorker, WorkerTimeoutError, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("email_mirror")
class MirrorWorker(QueueProcessingWorker):
    MAX_CONSUME_SECONDS = 5

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        rcpt_to = event["rcpt_to"]
        content = base64.b64decode(event["msg_base64"])
        msg = email.parser.BytesParser(_class=EmailMessage, policy=email.policy.default).parsebytes(
            content
        )
        if not is_missed_message_address(rcpt_to):
            # Missed message addresses are one-time use, so we don't need
            # to worry about emails to them resulting in message spam.
            recipient_realm = decode_stream_email_address(rcpt_to)[0].realm
            try:
                rate_limit_mirror_by_realm(recipient_realm)
            except RateLimitedError:
                logger.warning(
                    "MirrorWorker: Rejecting an email from: %s to realm: %s - rate limited.",
                    msg["From"],
                    recipient_realm.subdomain,
                )
                return

        try:
            mirror_email(msg, rcpt_to=rcpt_to)
        except WorkerTimeoutError:  # nocoverage
            logging.error(
                "Timed out ingesting message-id %s to %s (%d bytes) -- dropping!",
                msg["Message-ID"] or "<?>",
                rcpt_to,
                len(content),
            )
            return
