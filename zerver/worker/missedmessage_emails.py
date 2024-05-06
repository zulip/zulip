# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import threading
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, Optional

import sentry_sdk
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.db_connections import reset_queries
from zerver.lib.email_notifications import MissedMessageData, handle_missedmessage_emails
from zerver.lib.per_request_cache import flush_per_request_caches
from zerver.models import ScheduledMessageNotificationEmail
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("missedmessage_emails")
class MissedMessageWorker(QueueProcessingWorker):
    # Aggregate all messages received over the last several seconds
    # (configurable by each recipient) to let someone finish sending a
    # batch of messages and/or editing them before they are sent out
    # as emails to recipients.
    #
    # The batch interval is best-effort -- we poll at most every
    # CHECK_FREQUENCY_SECONDS, to avoid excessive activity.
    CHECK_FREQUENCY_SECONDS = 5

    worker_thread: Optional[threading.Thread] = None

    # This condition variable mediates the stopping and has_timeout
    # pieces of state, below it.
    cv = threading.Condition()
    stopping = False
    has_timeout = False

    # The main thread, which handles the RabbitMQ connection and creates
    # database rows from them.
    @override
    @sentry_sdk.trace
    def consume(self, event: Dict[str, Any]) -> None:
        logging.debug("Processing missedmessage_emails event: %s", event)
        # When we consume an event, check if there are existing pending emails
        # for that user, and if so use the same scheduled timestamp.

        user_profile_id: int = event["user_profile_id"]
        user_profile = get_user_profile_by_id(user_profile_id)
        batch_duration_seconds = user_profile.email_notifications_batching_period_seconds
        batch_duration = timedelta(seconds=batch_duration_seconds)

        try:
            pending_email = ScheduledMessageNotificationEmail.objects.filter(
                user_profile_id=user_profile_id
            )[0]
            scheduled_timestamp = pending_email.scheduled_timestamp
        except IndexError:
            scheduled_timestamp = timezone_now() + batch_duration

        with self.cv:
            # We now hold the lock, so there are three places the
            # worker thread can be:
            #
            #  1. In maybe_send_batched_emails, and will have to take
            #     the lock (and thus block insertions of new rows
            #     here) to decide if there are any rows and if it thus
            #     needs a timeout.
            #
            #  2. In the cv.wait_for with a timeout because there were
            #     rows already.  There's nothing for us to do, since
            #     the newly-inserted row will get checked upon that
            #     timeout.
            #
            #  3. In the cv.wait_for without a timeout, because there
            #     weren't any rows (which we're about to change).
            #
            # Notifying in (1) is irrelevant, since the thread is not
            # waiting.  If we over-notify by doing so for both (2) and
            # (3), the behaviour is correct but slightly inefficient,
            # as the thread will be needlessly awoken and will just
            # re-wait.  However, if we fail to awake case (3), the
            # worker thread will never wake up, and the
            # ScheduledMessageNotificationEmail internal queue will
            # back up.
            #
            # Use the self.has_timeout property (which is protected by
            # the lock) to determine which of cases (2) or (3) we are
            # in, and as such if we need to notify after making the
            # row.
            try:
                ScheduledMessageNotificationEmail.objects.create(
                    user_profile_id=user_profile_id,
                    message_id=event["message_id"],
                    trigger=event["trigger"],
                    scheduled_timestamp=scheduled_timestamp,
                    mentioned_user_group_id=event.get("mentioned_user_group_id"),
                )
                if not self.has_timeout:
                    self.cv.notify()
            except IntegrityError:
                logging.debug(
                    "ScheduledMessageNotificationEmail row could not be created. The message may have been deleted. Skipping event."
                )

    @override
    def start(self) -> None:
        with self.cv:
            self.stopping = False
        self.worker_thread = threading.Thread(target=self.work)
        self.worker_thread.start()
        super().start()

    def work(self) -> None:
        backoff = 1
        while True:
            with sentry_sdk.start_transaction(
                op="task",
                name=f"{self.queue_name} worker thread",
                custom_sampling_context={"queue": self.queue_name},
            ):
                flush_per_request_caches()
                reset_queries()
                try:
                    finished = self.background_loop()
                    if finished:
                        break
                    # Success running the background loop; reset our backoff
                    backoff = 1
                except Exception:
                    logging.exception(
                        "Exception in MissedMessage background worker; restarting the loop",
                        stack_info=True,
                    )

                    # We want to sleep, with backoff, before retrying
                    # the background loop; there may be
                    # non-recoverable errors which cause immediate
                    # exceptions, and we should avoid fast
                    # crash-looping.  Instead of using time.sleep,
                    # which would block this thread and delay attempts
                    # to exit, we wait on the condition variable.
                    # With has_timeout set, this will only be notified
                    # by .stop(), below.
                    #
                    # Generally, delays in this background process are
                    # acceptable, so long as they at least
                    # occasionally retry.
                    with self.cv:
                        self.has_timeout = True
                        self.cv.wait(timeout=backoff)
                    backoff = min(30, backoff * 2)

    def background_loop(self) -> bool:
        with self.cv:
            if self.stopping:
                return True
            # There are three conditions which we wait for:
            #
            #  1. We are being explicitly asked to stop; see the
            #     notify() call in stop()
            #
            #  2. We have no ScheduledMessageNotificationEmail
            #     objects currently (has_timeout = False) and the
            #     first one was just enqueued; see the notify()
            #     call in consume().  We break out so that we can
            #     come back around the loop and re-wait with a
            #     timeout (see next condition).
            #
            #  3. One or more ScheduledMessageNotificationEmail
            #     exist in the database, so we need to re-check
            #     them regularly; this happens by hitting the
            #     timeout and calling maybe_send_batched_emails().
            #     There is no explicit notify() for this.
            timeout: Optional[int] = None
            if ScheduledMessageNotificationEmail.objects.exists():
                timeout = self.CHECK_FREQUENCY_SECONDS
            self.has_timeout = timeout is not None

            def wait_condition() -> bool:
                if self.stopping:
                    # Condition (1)
                    return True
                if timeout is None:
                    # Condition (2).  We went to sleep with no
                    # ScheduledMessageNotificationEmail existing,
                    # and one has just been made.  We re-check
                    # that is still true now that we have the
                    # lock, and if we see it, we stop waiting.
                    return ScheduledMessageNotificationEmail.objects.exists()
                # This should only happen at the start or end of
                # the wait, when we haven't been notified, but are
                # re-checking the condition.
                return False

            with sentry_sdk.start_span(description="condvar wait") as span:
                span.set_data("timeout", timeout)
                was_notified = self.cv.wait_for(wait_condition, timeout=timeout)
                span.set_data("was_notified", was_notified)

        # Being notified means that we are in conditions (1) or
        # (2), above.  In neither case do we need to look at if
        # there are batches to send -- (2) means that the
        # ScheduledMessageNotificationEmail was _just_ created, so
        # there is no need to check it now.
        if not was_notified:
            self.maybe_send_batched_emails()

        return False

    @sentry_sdk.trace
    def maybe_send_batched_emails(self) -> None:
        current_time = timezone_now()

        with transaction.atomic():
            events_to_process = ScheduledMessageNotificationEmail.objects.filter(
                scheduled_timestamp__lte=current_time
            ).select_for_update()

            # Batch the entries by user
            events_by_recipient: Dict[int, Dict[int, MissedMessageData]] = defaultdict(dict)
            for event in events_to_process:
                events_by_recipient[event.user_profile_id][event.message_id] = MissedMessageData(
                    trigger=event.trigger, mentioned_user_group_id=event.mentioned_user_group_id
                )

            for user_profile_id in events_by_recipient:
                events = events_by_recipient[user_profile_id]

                logging.info(
                    "Batch-processing %s missedmessage_emails events for user %s",
                    len(events),
                    user_profile_id,
                )
                with sentry_sdk.start_span(
                    description="sending missedmessage_emails to user"
                ) as span:
                    span.set_data("user_profile_id", user_profile_id)
                    span.set_data("event_count", len(events))
                    try:
                        # Because we process events in batches, an
                        # escaped exception here would lead to
                        # duplicate messages being sent for other
                        # users in the same events_to_process batch,
                        # and no guarantee of forward progress.
                        handle_missedmessage_emails(user_profile_id, events)
                    except Exception:
                        logging.exception(
                            "Failed to process %d missedmessage_emails for user %s",
                            len(events),
                            user_profile_id,
                            stack_info=True,
                        )

            events_to_process.delete()

    @override
    def stop(self) -> None:
        with self.cv:
            self.stopping = True
            self.cv.notify()
        if self.worker_thread is not None:
            self.worker_thread.join()
        super().stop()
