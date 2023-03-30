# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import base64
import copy
import datetime
import email
import email.policy
import functools
import logging
import os
import signal
import socket
import tempfile
import threading
import time
import urllib
from abc import ABC, abstractmethod
from collections import deque
from email.message import EmailMessage
from functools import wraps
from types import FrameType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
)

import orjson
import sentry_sdk
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.db import connection, transaction
from django.db.models import F
from django.db.utils import IntegrityError
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from sentry_sdk import add_breadcrumb, configure_scope
from zulip_bots.lib import extract_query_without_mention

from zerver.actions.invites import do_send_confirmation_email
from zerver.actions.message_edit import do_update_embedded_data
from zerver.actions.message_flags import do_mark_stream_messages_as_read
from zerver.actions.message_send import internal_send_private_message, render_incoming_message
from zerver.actions.presence import do_update_user_presence
from zerver.actions.realm_export import notify_realm_export
from zerver.actions.user_activity import do_update_user_activity, do_update_user_activity_interval
from zerver.context_processors import common_context
from zerver.lib.bot_lib import EmbeddedBotHandler, EmbeddedBotQuitError, get_bot_handler
from zerver.lib.context_managers import lockfile
from zerver.lib.db import reset_queries
from zerver.lib.digest import bulk_handle_digest_email
from zerver.lib.email_mirror import (
    decode_stream_email_address,
    is_missed_message_address,
    rate_limit_mirror_by_realm,
)
from zerver.lib.email_mirror import process_message as mirror_email
from zerver.lib.email_notifications import handle_missedmessage_emails
from zerver.lib.error_notify import do_report_error
from zerver.lib.exceptions import RateLimitedError
from zerver.lib.export import export_realm_wrapper
from zerver.lib.outgoing_webhook import do_rest_call, get_outgoing_webhook_service_handler
from zerver.lib.push_notifications import (
    clear_push_device_tokens,
    handle_push_notification,
    handle_remove_push_notification,
    initialize_push_notifications,
)
from zerver.lib.pysa import mark_sanitized
from zerver.lib.queue import SimpleQueueClient, retry_event
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.lib.send_email import (
    EmailNotDeliveredError,
    FromAddress,
    handle_send_email_format_changes,
    initialize_connection,
    send_email,
    send_future_email,
)
from zerver.lib.soft_deactivation import reactivate_user_if_soft_deactivated
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.upload import handle_reupload_emojis_event
from zerver.lib.url_preview import preview as url_preview
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.models import (
    Message,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    ScheduledMessageNotificationEmail,
    UserMessage,
    UserProfile,
    filter_to_valid_prereg_users,
    flush_per_request_caches,
    get_bot_services,
    get_client,
    get_system_bot,
    get_user_profile_by_id,
)

logger = logging.getLogger(__name__)


class WorkerTimeoutError(Exception):
    def __init__(self, queue_name: str, limit: int, event_count: int) -> None:
        self.queue_name = queue_name
        self.limit = limit
        self.event_count = event_count

    def __str__(self) -> str:
        return f"Timed out in {self.queue_name} after {self.limit * self.event_count} seconds processing {self.event_count} events"


class InterruptConsumeError(Exception):
    """
    This exception is to be thrown inside event consume function
    if the intention is to simply interrupt the processing
    of the current event and normally continue the work of the queue.
    """

    pass


class WorkerDeclarationError(Exception):
    pass


ConcreteQueueWorker = TypeVar("ConcreteQueueWorker", bound="QueueProcessingWorker")


def assign_queue(
    queue_name: str,
    enabled: bool = True,
    is_test_queue: bool = False,
) -> Callable[[Type[ConcreteQueueWorker]], Type[ConcreteQueueWorker]]:
    def decorate(clazz: Type[ConcreteQueueWorker]) -> Type[ConcreteQueueWorker]:
        clazz.queue_name = queue_name
        if enabled:
            register_worker(queue_name, clazz, is_test_queue)
        return clazz

    return decorate


worker_classes: Dict[str, Type["QueueProcessingWorker"]] = {}
test_queues: Set[str] = set()


def register_worker(
    queue_name: str, clazz: Type["QueueProcessingWorker"], is_test_queue: bool = False
) -> None:
    worker_classes[queue_name] = clazz
    if is_test_queue:
        test_queues.add(queue_name)


def get_worker(queue_name: str) -> "QueueProcessingWorker":
    return worker_classes[queue_name]()


def get_active_worker_queues(only_test_queues: bool = False) -> List[str]:
    """Returns all (either test, or real) worker queues."""
    return [
        queue_name
        for queue_name in worker_classes.keys()
        if bool(queue_name in test_queues) == only_test_queues
    ]


def check_and_send_restart_signal() -> None:
    try:
        if not connection.is_usable():
            logging.warning("*** Sending self SIGUSR1 to trigger a restart.")
            os.kill(os.getpid(), signal.SIGUSR1)
    except Exception:
        pass


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
        except (
            socket.gaierror,
            socket.timeout,
            EmailNotDeliveredError,
        ) as e:
            error_class_name = type(e).__name__

            def on_failure(event: Dict[str, Any]) -> None:
                logging.exception(
                    "Event %r failed due to exception %s", event, error_class_name, stack_info=True
                )

            retry_event(worker.queue_name, data, on_failure)

    return wrapper


class QueueProcessingWorker(ABC):
    queue_name: str
    MAX_CONSUME_SECONDS: Optional[int] = 30
    # The MAX_CONSUME_SECONDS timeout is only enabled when handling a
    # single queue at once, with no threads.
    ENABLE_TIMEOUTS = False
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 50
    MAX_SECONDS_BEFORE_UPDATE_STATS = 30

    # How many un-acknowledged events the worker should have on hand,
    # fetched from the rabbitmq server.  Larger values may be more
    # performant, but if queues are large, cause more network IO at
    # startup and steady-state memory.
    PREFETCH = 100

    def __init__(self) -> None:
        self.q: Optional[SimpleQueueClient] = None
        if not hasattr(self, "queue_name"):
            raise WorkerDeclarationError("Queue worker declared without queue_name")

        self.initialize_statistics()

    def initialize_statistics(self) -> None:
        self.queue_last_emptied_timestamp = time.time()
        self.consumed_since_last_emptied = 0
        self.recent_consume_times: MutableSequence[Tuple[int, float]] = deque(maxlen=50)
        self.consume_iteration_counter = 0
        self.idle = True
        self.last_statistics_update_time = 0.0

        self.update_statistics()

    def update_statistics(self) -> None:
        total_seconds = sum(seconds for _, seconds in self.recent_consume_times)
        total_events = sum(events_number for events_number, _ in self.recent_consume_times)
        if total_events == 0:
            recent_average_consume_time = None
        else:
            recent_average_consume_time = total_seconds / total_events
        stats_dict = dict(
            update_time=time.time(),
            recent_average_consume_time=recent_average_consume_time,
            queue_last_emptied_timestamp=self.queue_last_emptied_timestamp,
            consumed_since_last_emptied=self.consumed_since_last_emptied,
        )

        os.makedirs(settings.QUEUE_STATS_DIR, exist_ok=True)

        fname = f"{self.queue_name}.stats"
        fn = os.path.join(settings.QUEUE_STATS_DIR, fname)
        with lockfile(fn + ".lock"):
            tmp_fn = fn + ".tmp"
            with open(tmp_fn, "wb") as f:
                f.write(
                    orjson.dumps(stats_dict, option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2)
                )
            os.rename(tmp_fn, fn)
        self.last_statistics_update_time = time.time()

    def get_remaining_local_queue_size(self) -> int:
        if self.q is not None:
            return self.q.local_queue_size()
        else:
            # This is a special case that will happen if we're operating without
            # using RabbitMQ (e.g. in tests). In that case there's no queuing to speak of
            # and the only reasonable size to return is 0.
            return 0

    @abstractmethod
    def consume(self, data: Dict[str, Any]) -> None:
        pass

    def do_consume(
        self, consume_func: Callable[[List[Dict[str, Any]]], None], events: List[Dict[str, Any]]
    ) -> None:
        consume_time_seconds: Optional[float] = None
        with configure_scope() as scope:
            scope.clear_breadcrumbs()
            add_breadcrumb(
                type="debug",
                category="queue_processor",
                message=f"Consuming {self.queue_name}",
                data={"events": events, "local_queue_size": self.get_remaining_local_queue_size()},
            )
        try:
            if self.idle:
                # We're reactivating after having gone idle due to emptying the queue.
                # We should update the stats file to keep it fresh and to make it clear
                # that the queue started processing, in case the event we're about to process
                # makes us freeze.
                self.idle = False
                self.update_statistics()

            time_start = time.time()
            if self.MAX_CONSUME_SECONDS and self.ENABLE_TIMEOUTS:
                try:
                    signal.signal(
                        signal.SIGALRM,
                        functools.partial(self.timer_expired, self.MAX_CONSUME_SECONDS, events),
                    )
                    try:
                        signal.alarm(self.MAX_CONSUME_SECONDS * len(events))
                        consume_func(events)
                    finally:
                        signal.alarm(0)
                finally:
                    signal.signal(signal.SIGALRM, signal.SIG_DFL)
            else:
                consume_func(events)
            consume_time_seconds = time.time() - time_start
            self.consumed_since_last_emptied += len(events)
        except Exception as e:
            self._handle_consume_exception(events, e)
        finally:
            flush_per_request_caches()
            reset_queries()

            if consume_time_seconds is not None:
                self.recent_consume_times.append((len(events), consume_time_seconds))

            remaining_local_queue_size = self.get_remaining_local_queue_size()
            if remaining_local_queue_size == 0:
                self.queue_last_emptied_timestamp = time.time()
                self.consumed_since_last_emptied = 0
                # We've cleared all the events from the queue, so we don't
                # need to worry about the small overhead of doing a disk write.
                # We take advantage of this to update the stats file to keep it fresh,
                # especially since the queue might go idle until new events come in.
                self.update_statistics()
                self.idle = True
            else:
                self.consume_iteration_counter += 1
                if (
                    self.consume_iteration_counter
                    >= self.CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM
                    or time.time() - self.last_statistics_update_time
                    >= self.MAX_SECONDS_BEFORE_UPDATE_STATS
                ):
                    self.consume_iteration_counter = 0
                    self.update_statistics()

    def consume_single_event(self, event: Dict[str, Any]) -> None:
        consume_func = lambda events: self.consume(events[0])
        self.do_consume(consume_func, [event])

    def timer_expired(
        self, limit: int, events: List[Dict[str, Any]], signal: int, frame: FrameType
    ) -> None:
        raise WorkerTimeoutError(self.queue_name, limit, len(events))

    def _handle_consume_exception(self, events: List[Dict[str, Any]], exception: Exception) -> None:
        if isinstance(exception, InterruptConsumeError):
            # The exception signals that no further error handling
            # is needed and the worker can proceed.
            return

        with configure_scope() as scope:
            scope.set_context(
                "events",
                {
                    "data": events,
                    "queue_name": self.queue_name,
                },
            )
            if isinstance(exception, WorkerTimeoutError):
                with sentry_sdk.push_scope() as scope:
                    scope.fingerprint = ["worker-timeout", self.queue_name]
                    logging.exception(exception, stack_info=True)
            else:
                logging.exception(
                    "Problem handling data on queue %s", self.queue_name, stack_info=True
                )
        if not os.path.exists(settings.QUEUE_ERROR_DIR):
            os.mkdir(settings.QUEUE_ERROR_DIR)  # nocoverage
        # Use 'mark_sanitized' to prevent Pysa from detecting this false positive
        # flow. 'queue_name' is always a constant string.
        fname = mark_sanitized(f"{self.queue_name}.errors")
        fn = os.path.join(settings.QUEUE_ERROR_DIR, fname)
        line = f"{time.asctime()}\t{orjson.dumps(events).decode()}\n"
        lock_fn = fn + ".lock"
        with lockfile(lock_fn):
            with open(fn, "a") as f:
                f.write(line)
        check_and_send_restart_signal()

    def setup(self) -> None:
        self.q = SimpleQueueClient(prefetch=self.PREFETCH)

    def start(self) -> None:
        assert self.q is not None
        self.initialize_statistics()
        self.q.start_json_consumer(
            self.queue_name,
            lambda events: self.consume_single_event(events[0]),
        )

    def stop(self) -> None:  # nocoverage
        assert self.q is not None
        self.q.stop_consuming()


class LoopQueueProcessingWorker(QueueProcessingWorker):
    sleep_delay = 1
    batch_size = 100

    def setup(self) -> None:
        self.q = SimpleQueueClient(prefetch=max(self.PREFETCH, self.batch_size))

    def start(self) -> None:  # nocoverage
        assert self.q is not None
        self.initialize_statistics()
        self.q.start_json_consumer(
            self.queue_name,
            lambda events: self.do_consume(self.consume_batch, events),
            batch_size=self.batch_size,
            timeout=self.sleep_delay,
        )

    @abstractmethod
    def consume_batch(self, events: List[Dict[str, Any]]) -> None:
        pass

    def consume(self, event: Dict[str, Any]) -> None:
        """In LoopQueueProcessingWorker, consume is used just for automated tests"""
        self.consume_batch([event])


@assign_queue("invites")
class ConfirmationEmailWorker(QueueProcessingWorker):
    def consume(self, data: Mapping[str, Any]) -> None:
        if "invite_expires_in_days" in data:
            invite_expires_in_minutes = data["invite_expires_in_days"] * 24 * 60
        elif "invite_expires_in_minutes" in data:
            invite_expires_in_minutes = data["invite_expires_in_minutes"]
        invitee = filter_to_valid_prereg_users(
            PreregistrationUser.objects.filter(id=data["prereg_id"]), invite_expires_in_minutes
        ).first()
        if invitee is None:
            # The invitation could have been revoked
            return

        referrer = get_user_profile_by_id(data["referrer_id"])
        logger.info(
            "Sending invitation for realm %s to %s", referrer.realm.string_id, invitee.email
        )
        if "email_language" in data:
            email_language = data["email_language"]
        else:
            email_language = referrer.realm.default_language

        activate_url = do_send_confirmation_email(
            invitee, referrer, email_language, invite_expires_in_minutes
        )
        if invite_expires_in_minutes is None:
            # We do not queue reminder email for never expiring
            # invitations. This is probably a low importance bug; it
            # would likely be more natural to send a reminder after 7
            # days.
            return

        # queue invitation reminder
        if invite_expires_in_minutes >= 4 * 24 * 60:
            context = common_context(referrer)
            context.update(
                activate_url=activate_url,
                referrer_name=referrer.full_name,
                referrer_email=referrer.delivery_email,
                referrer_realm_name=referrer.realm.name,
            )
            send_future_email(
                "zerver/emails/invitation_reminder",
                referrer.realm,
                to_emails=[invitee.email],
                from_address=FromAddress.tokenized_no_reply_placeholder,
                language=email_language,
                context=context,
                delay=datetime.timedelta(minutes=invite_expires_in_minutes - (2 * 24 * 60)),
            )


@assign_queue("user_activity")
class UserActivityWorker(LoopQueueProcessingWorker):
    """The UserActivity queue is perhaps our highest-traffic queue, and
    requires some care to ensure it performs adequately.

    We use a LoopQueueProcessingWorker as a performance optimization
    for managing the queue.  The structure of UserActivity records is
    such that they are easily deduplicated before being sent to the
    database; we take advantage of that to make this queue highly
    effective at dealing with a backlog containing many similar
    events.  Such a backlog happen in a few ways:

    * In abuse/DoS situations, if a client is sending huge numbers of
      similar requests to the server.
    * If the queue ends up with several minutes of backlog e.g. due to
      downtime of the queue processor, many clients will have several
      common events from doing an action multiple times.

    """

    client_id_map: Dict[str, int] = {}

    def start(self) -> None:
        # For our unit tests to make sense, we need to clear this on startup.
        self.client_id_map = {}
        super().start()

    def consume_batch(self, user_activity_events: List[Dict[str, Any]]) -> None:
        uncommitted_events: Dict[Tuple[int, int, str], Tuple[int, float]] = {}

        # First, we drain the queue of all user_activity events and
        # deduplicate them for insertion into the database.
        for event in user_activity_events:
            user_profile_id = event["user_profile_id"]
            client_id = event["client_id"]

            key_tuple = (user_profile_id, client_id, event["query"])
            if key_tuple not in uncommitted_events:
                uncommitted_events[key_tuple] = (1, event["time"])
            else:
                count, time = uncommitted_events[key_tuple]
                uncommitted_events[key_tuple] = (count + 1, max(time, event["time"]))

        # Then we insert the updates into the database.
        #
        # TODO: Doing these updates in sequence individually is likely
        # inefficient; the idealized version would do some sort of
        # bulk insert_or_update query.
        for key_tuple in uncommitted_events:
            (user_profile_id, client_id, query) = key_tuple
            count, time = uncommitted_events[key_tuple]
            log_time = timestamp_to_datetime(time)
            do_update_user_activity(user_profile_id, client_id, query, count, log_time)


@assign_queue("user_activity_interval")
class UserActivityIntervalWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        log_time = timestamp_to_datetime(event["time"])
        do_update_user_activity_interval(user_profile, log_time)


@assign_queue("user_presence")
class UserPresenceWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.debug("Received presence event: %s", event)
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        status = event["status"]
        do_update_user_presence(user_profile, client, log_time, status)


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
    def consume(self, event: Dict[str, Any]) -> None:
        logging.debug("Processing missedmessage_emails event: %s", event)
        # When we consume an event, check if there are existing pending emails
        # for that user, and if so use the same scheduled timestamp.
        user_profile_id: int = event["user_profile_id"]
        user_profile = get_user_profile_by_id(user_profile_id)
        batch_duration_seconds = user_profile.email_notifications_batching_period_seconds
        batch_duration = datetime.timedelta(seconds=batch_duration_seconds)

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

    def start(self) -> None:
        with self.cv:
            self.stopping = False
        self.worker_thread = threading.Thread(target=lambda: self.work())
        self.worker_thread.start()
        super().start()

    def work(self) -> None:
        while True:
            with self.cv:
                if self.stopping:
                    return
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

                was_notified = self.cv.wait_for(wait_condition, timeout=timeout)

            # Being notified means that we are in conditions (1) or
            # (2), above.  In neither case do we need to look at if
            # there are batches to send -- (2) means that the
            # ScheduledMessageNotificationEmail was _just_ created, so
            # there is no need to check it now.
            if not was_notified:
                self.maybe_send_batched_emails()

    def maybe_send_batched_emails(self) -> None:
        current_time = timezone_now()

        with transaction.atomic():
            events_to_process = ScheduledMessageNotificationEmail.objects.filter(
                scheduled_timestamp__lte=current_time
            ).select_related()

            # Batch the entries by user
            events_by_recipient: Dict[int, List[Dict[str, Any]]] = {}
            for event in events_to_process:
                entry = dict(
                    user_profile_id=event.user_profile_id,
                    message_id=event.message_id,
                    trigger=event.trigger,
                    mentioned_user_group_id=event.mentioned_user_group_id,
                )
                if event.user_profile_id in events_by_recipient:
                    events_by_recipient[event.user_profile_id].append(entry)
                else:
                    events_by_recipient[event.user_profile_id] = [entry]

            for user_profile_id in events_by_recipient:
                events: List[Dict[str, Any]] = events_by_recipient[user_profile_id]

                logging.info(
                    "Batch-processing %s missedmessage_emails events for user %s",
                    len(events),
                    user_profile_id,
                )
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

    def stop(self) -> None:
        with self.cv:
            self.stopping = True
            self.cv.notify()
        if self.worker_thread is not None:
            self.worker_thread.join()
        super().stop()


@assign_queue("email_senders")
class EmailSendingWorker(LoopQueueProcessingWorker):
    def __init__(self) -> None:
        super().__init__()
        self.connection: BaseEmailBackend = initialize_connection(None)

    @retry_send_email_failures
    def send_email(self, event: Dict[str, Any]) -> None:
        # Copy the event, so that we don't pass the `failed_tries'
        # data to send_email (which neither takes that
        # argument nor needs that data).
        copied_event = copy.deepcopy(event)
        if "failed_tries" in copied_event:
            del copied_event["failed_tries"]
        handle_send_email_format_changes(copied_event)
        self.connection = initialize_connection(self.connection)
        send_email(**copied_event, connection=self.connection)

    def consume_batch(self, events: List[Dict[str, Any]]) -> None:
        for event in events:
            self.send_email(event)

    def stop(self) -> None:
        try:
            self.connection.close()
        finally:
            super().stop()


@assign_queue("missedmessage_mobile_notifications")
class PushNotificationsWorker(QueueProcessingWorker):
    # The use of aioapns in the backend means that we cannot use
    # SIGALRM to limit how long a consume takes, as SIGALRM does not
    # play well with asyncio.
    MAX_CONSUME_SECONDS = None

    def start(self) -> None:
        # initialize_push_notifications doesn't strictly do anything
        # beyond printing some logging warnings if push notifications
        # are not available in the current configuration.
        initialize_push_notifications()
        super().start()

    def consume(self, event: Dict[str, Any]) -> None:
        try:
            if event.get("type", "add") == "remove":
                message_ids = event["message_ids"]
                handle_remove_push_notification(event["user_profile_id"], message_ids)
            else:
                handle_push_notification(event["user_profile_id"], event)
        except PushNotificationBouncerRetryLaterError:

            def failure_processor(event: Dict[str, Any]) -> None:
                logger.warning(
                    "Maximum retries exceeded for trigger:%s event:push_notification",
                    event["user_profile_id"],
                )

            retry_event(self.queue_name, event, failure_processor)


@assign_queue("error_reports")
class ErrorReporter(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        error_types = ["browser", "server"]
        assert event["type"] in error_types

        logging.info(
            "Processing traceback with type %s for %s", event["type"], event.get("user_email")
        )
        if settings.ERROR_REPORTING:
            do_report_error(event["type"], event["report"])


@assign_queue("digest_emails")
class DigestWorker(QueueProcessingWorker):  # nocoverage
    # Who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    def consume(self, event: Mapping[str, Any]) -> None:
        if "user_ids" in event:
            user_ids = event["user_ids"]
        else:
            # legacy code may have enqueued a single id
            user_ids = [event["user_profile_id"]]
        bulk_handle_digest_email(user_ids, event["cutoff"])


@assign_queue("email_mirror")
class MirrorWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        rcpt_to = event["rcpt_to"]
        msg = email.message_from_bytes(
            base64.b64decode(event["msg_base64"]),
            policy=email.policy.default,
        )
        assert isinstance(msg, EmailMessage)  # https://github.com/python/typeshed/issues/2417
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

        mirror_email(msg, rcpt_to=rcpt_to)


@assign_queue("embed_links")
class FetchLinksEmbedData(QueueProcessingWorker):
    # This is a slow queue with network requests, so a disk write is negligible.
    # Update stats file after every consume call.
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 1

    def consume(self, event: Mapping[str, Any]) -> None:
        url_embed_data: Dict[str, Optional[UrlEmbedData]] = {}
        for url in event["urls"]:
            start_time = time.time()
            url_embed_data[url] = url_preview.get_link_embed_data(url)
            logging.info(
                "Time spent on get_link_embed_data for %s: %s", url, time.time() - start_time
            )

        with transaction.atomic():
            try:
                message = Message.objects.select_for_update().get(id=event["message_id"])
            except Message.DoesNotExist:
                # Message may have been deleted
                return

            # If the message changed, we will run this task after updating the message
            # in zerver.actions.message_edit.check_update_message
            if message.content != event["message_content"]:
                return

            # Fetch the realm whose settings we're using for rendering
            realm = Realm.objects.get(id=event["message_realm_id"])

            # If rendering fails, the called code will raise a JsonableError.
            rendering_result = render_incoming_message(
                message,
                message.content,
                realm,
                url_embed_data=url_embed_data,
            )
            do_update_embedded_data(message.sender, message, message.content, rendering_result)

    def timer_expired(
        self, limit: int, events: List[Dict[str, Any]], signal: int, frame: FrameType
    ) -> None:
        assert len(events) == 1
        event = events[0]

        logging.warning(
            "Timed out in %s after %s seconds while fetching URLs for message %s: %s",
            self.queue_name,
            limit,
            event["message_id"],
            event["urls"],
        )
        raise InterruptConsumeError


@assign_queue("outgoing_webhooks")
class OutgoingWebhookWorker(QueueProcessingWorker):
    def consume(self, event: Dict[str, Any]) -> None:
        message = event["message"]
        event["command"] = message["content"]

        services = get_bot_services(event["user_profile_id"])
        for service in services:
            event["service_name"] = str(service.name)
            service_handler = get_outgoing_webhook_service_handler(service)
            do_rest_call(service.base_url, event, service_handler)


@assign_queue("embedded_bots")
class EmbeddedBotWorker(QueueProcessingWorker):
    def get_bot_api_client(self, user_profile: UserProfile) -> EmbeddedBotHandler:
        return EmbeddedBotHandler(user_profile)

    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile_id = event["user_profile_id"]
        user_profile = get_user_profile_by_id(user_profile_id)

        message: Dict[str, Any] = event["message"]

        # TODO: Do we actually want to allow multiple Services per bot user?
        services = get_bot_services(user_profile_id)
        for service in services:
            bot_handler = get_bot_handler(str(service.name))
            if bot_handler is None:
                logging.error(
                    "Error: User %s has bot with invalid embedded bot service %s",
                    user_profile_id,
                    service.name,
                )
                continue
            try:
                if hasattr(bot_handler, "initialize"):
                    bot_handler.initialize(self.get_bot_api_client(user_profile))
                if event["trigger"] == "mention":
                    message["content"] = extract_query_without_mention(
                        message=message,
                        client=self.get_bot_api_client(user_profile),
                    )
                    assert message["content"] is not None
                bot_handler.handle_message(
                    message=message,
                    bot_handler=self.get_bot_api_client(user_profile),
                )
            except EmbeddedBotQuitError as e:
                logging.warning("%s", e)


@assign_queue("deferred_work")
class DeferredWorker(QueueProcessingWorker):
    """This queue processor is intended for cases where we want to trigger a
    potentially expensive, not urgent, job to be run on a separate
    thread from the Django worker that initiated it (E.g. so we that
    can provide a low-latency HTTP response or avoid risk of request
    timeouts for an operation that could in rare cases take minutes).
    """

    # Because these operations have no SLO, and can take minutes,
    # remove any processing timeouts
    MAX_CONSUME_SECONDS = None

    def consume(self, event: Dict[str, Any]) -> None:
        start = time.time()
        if event["type"] == "mark_stream_messages_as_read":
            user_profile = get_user_profile_by_id(event["user_profile_id"])

            for recipient_id in event["stream_recipient_ids"]:
                count = do_mark_stream_messages_as_read(user_profile, recipient_id)
                logger.info(
                    "Marked %s messages as read for user %s, stream_recipient_id %s",
                    count,
                    user_profile.id,
                    recipient_id,
                )
        elif event["type"] == "mark_stream_messages_as_read_for_everyone":
            # This event is generated by the stream deactivation code path.
            batch_size = 100
            offset = 0
            while True:
                messages = Message.objects.filter(
                    recipient_id=event["stream_recipient_id"]
                ).order_by("id")[offset : offset + batch_size]

                with transaction.atomic(savepoint=False):
                    UserMessage.select_for_update_query().filter(message__in=messages).extra(
                        where=[UserMessage.where_unread()]
                    ).update(flags=F("flags").bitor(UserMessage.flags.read))
                offset += len(messages)
                if len(messages) < batch_size:
                    break
            logger.info(
                "Marked %s messages as read for all users, stream_recipient_id %s",
                offset,
                event["stream_recipient_id"],
            )
        elif event["type"] == "clear_push_device_tokens":
            try:
                clear_push_device_tokens(event["user_profile_id"])
            except PushNotificationBouncerRetryLaterError:

                def failure_processor(event: Dict[str, Any]) -> None:
                    logger.warning(
                        "Maximum retries exceeded for trigger:%s event:clear_push_device_tokens",
                        event["user_profile_id"],
                    )

                retry_event(self.queue_name, event, failure_processor)
        elif event["type"] == "realm_export":
            realm = Realm.objects.get(id=event["realm_id"])
            output_dir = tempfile.mkdtemp(prefix="zulip-export-")
            export_event = RealmAuditLog.objects.get(id=event["id"])
            user_profile = get_user_profile_by_id(event["user_profile_id"])

            try:
                public_url = export_realm_wrapper(
                    realm=realm,
                    output_dir=output_dir,
                    threads=6,
                    upload=True,
                    public_only=True,
                )
            except Exception:
                export_event.extra_data = orjson.dumps(
                    dict(
                        failed_timestamp=timezone_now().timestamp(),
                    )
                ).decode()
                export_event.save(update_fields=["extra_data"])
                logging.exception(
                    "Data export for %s failed after %s",
                    user_profile.realm.string_id,
                    time.time() - start,
                    stack_info=True,
                )
                notify_realm_export(user_profile)
                return

            assert public_url is not None

            # Update the extra_data field now that the export is complete.
            export_event.extra_data = orjson.dumps(
                dict(
                    export_path=urllib.parse.urlparse(public_url).path,
                )
            ).decode()
            export_event.save(update_fields=["extra_data"])

            # Send a private message notification letting the user who
            # triggered the export know the export finished.
            with override_language(user_profile.default_language):
                content = _(
                    "Your data export is complete and has been uploaded here:\n\n{public_url}"
                ).format(public_url=public_url)
            internal_send_private_message(
                sender=get_system_bot(settings.NOTIFICATION_BOT, realm.id),
                recipient_user=user_profile,
                content=content,
            )

            # For future frontend use, also notify administrator
            # clients that the export happened.
            notify_realm_export(user_profile)
            logging.info(
                "Completed data export for %s in %s",
                user_profile.realm.string_id,
                time.time() - start,
            )
        elif event["type"] == "reupload_realm_emoji":
            # This is a special event queued by the migration for reuploading emojis.
            # We don't want to run the necessary code in the actual migration, so it simply
            # queues the necessary event, and the actual work is done here in the queue worker.
            realm = Realm.objects.get(id=event["realm_id"])
            logger.info("Processing reupload_realm_emoji event for realm %s", realm.id)
            handle_reupload_emojis_event(realm, logger)
        elif event["type"] == "soft_reactivate":
            user_profile = get_user_profile_by_id(event["user_profile_id"])
            reactivate_user_if_soft_deactivated(user_profile)

        end = time.time()
        logger.info("deferred_work processed %s event (%dms)", event["type"], (end - start) * 1000)


@assign_queue("test", is_test_queue=True)
class TestWorker(QueueProcessingWorker):
    # This worker allows you to test the queue worker infrastructure without
    # creating significant side effects.  It can be useful in development or
    # for troubleshooting prod/staging.  It pulls a message off the test queue
    # and appends it to a file in /tmp.
    def consume(self, event: Mapping[str, Any]) -> None:  # nocoverage
        fn = settings.ZULIP_WORKER_TEST_FILE
        message = orjson.dumps(event)
        logging.info("TestWorker should append this message to %s: %s", fn, message.decode())
        with open(fn, "ab") as f:
            f.write(message + b"\n")


@assign_queue("noop", is_test_queue=True)
class NoopWorker(QueueProcessingWorker):
    """Used to profile the queue processing framework, in zilencer's queue_rate."""

    def __init__(self, max_consume: int = 1000, slow_queries: Sequence[int] = []) -> None:
        self.consumed = 0
        self.max_consume = max_consume
        self.slow_queries: Set[int] = set(slow_queries)

    def consume(self, event: Mapping[str, Any]) -> None:
        self.consumed += 1
        if self.consumed in self.slow_queries:
            logging.info("Slow request...")
            time.sleep(60)
            logging.info("Done!")
        if self.consumed >= self.max_consume:
            self.stop()


@assign_queue("noop_batch", is_test_queue=True)
class BatchNoopWorker(LoopQueueProcessingWorker):
    """Used to profile the queue processing framework, in zilencer's queue_rate."""

    batch_size = 100

    def __init__(self, max_consume: int = 1000, slow_queries: Sequence[int] = []) -> None:
        self.consumed = 0
        self.max_consume = max_consume
        self.slow_queries: Set[int] = set(slow_queries)

    def consume_batch(self, events: List[Dict[str, Any]]) -> None:
        event_numbers = set(range(self.consumed + 1, self.consumed + 1 + len(events)))
        found_slow = self.slow_queries & event_numbers
        if found_slow:
            logging.info("%d slow requests...", len(found_slow))
            time.sleep(60 * len(found_slow))
            logging.info("Done!")
        self.consumed += len(events)
        if self.consumed >= self.max_consume:
            self.stop()
