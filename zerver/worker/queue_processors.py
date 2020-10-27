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
import smtplib
import socket
import tempfile
import time
import urllib
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from email.message import EmailMessage
from functools import wraps
from threading import Lock, Timer
from types import FrameType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableSequence,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    cast,
)

import orjson
import requests
import sentry_sdk
from django.conf import settings
from django.db import connection
from django.db.models import F
from django.utils.timezone import now as timezone_now
from django.utils.translation import override as override_language
from django.utils.translation import ugettext as _
from sentry_sdk import add_breadcrumb, configure_scope
from zulip_bots.lib import ExternalBotHandler, extract_query_without_mention

from zerver.context_processors import common_context
from zerver.lib.actions import (
    do_mark_stream_messages_as_read,
    do_send_confirmation_email,
    do_update_embedded_data,
    do_update_user_activity,
    do_update_user_activity_interval,
    do_update_user_presence,
    internal_send_private_message,
    notify_realm_export,
    render_incoming_message,
)
from zerver.lib.bot_lib import EmbeddedBotHandler, EmbeddedBotQuitException, get_bot_handler
from zerver.lib.context_managers import lockfile
from zerver.lib.db import reset_queries
from zerver.lib.digest import handle_digest_email
from zerver.lib.email_mirror import decode_stream_email_address, is_missed_message_address
from zerver.lib.email_mirror import process_message as mirror_email
from zerver.lib.email_mirror import rate_limit_mirror_by_realm
from zerver.lib.email_notifications import handle_missedmessage_emails
from zerver.lib.error_notify import do_report_error
from zerver.lib.exceptions import RateLimited
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
    EmailNotDeliveredException,
    FromAddress,
    handle_send_email_format_changes,
    send_email_from_dict,
    send_future_email,
)
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.url_preview import preview as url_preview
from zerver.models import (
    Message,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
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

class WorkerTimeoutException(Exception):
    def __init__(self, limit: int, event_count: int) -> None:
        self.limit = limit
        self.event_count = event_count

    def __str__(self) -> str:
        return f"Timed out after {self.limit * self.event_count} seconds processing {self.event_count} events"

class WorkerDeclarationException(Exception):
    pass

ConcreteQueueWorker = TypeVar('ConcreteQueueWorker', bound='QueueProcessingWorker')

def assign_queue(
        queue_name: str, enabled: bool=True, is_test_queue: bool=False,
) -> Callable[[Type[ConcreteQueueWorker]], Type[ConcreteQueueWorker]]:
    def decorate(clazz: Type[ConcreteQueueWorker]) -> Type[ConcreteQueueWorker]:
        clazz.queue_name = queue_name
        if enabled:
            register_worker(queue_name, clazz, is_test_queue)
        return clazz
    return decorate

worker_classes: Dict[str, Type["QueueProcessingWorker"]] = {}
test_queues: Set[str] = set()
def register_worker(queue_name: str, clazz: Type['QueueProcessingWorker'], is_test_queue: bool=False) -> None:
    worker_classes[queue_name] = clazz
    if is_test_queue:
        test_queues.add(queue_name)

def get_worker(queue_name: str) -> 'QueueProcessingWorker':
    return worker_classes[queue_name]()

def get_active_worker_queues(only_test_queues: bool=False) -> List[str]:
    """Returns all (either test, or real) worker queues."""
    return [queue_name for queue_name in worker_classes.keys()
            if bool(queue_name in test_queues) == only_test_queues]

def check_and_send_restart_signal() -> None:
    try:
        if not connection.is_usable():
            logging.warning("*** Sending self SIGUSR1 to trigger a restart.")
            os.kill(os.getpid(), signal.SIGUSR1)
    except Exception:
        pass

def retry_send_email_failures(
        func: Callable[[ConcreteQueueWorker, Dict[str, Any]], None],
) -> Callable[['QueueProcessingWorker', Dict[str, Any]], None]:

    @wraps(func)
    def wrapper(worker: ConcreteQueueWorker, data: Dict[str, Any]) -> None:
        try:
            func(worker, data)
        except (smtplib.SMTPServerDisconnected, socket.gaierror, socket.timeout,
                EmailNotDeliveredException) as e:
            error_class_name = e.__class__.__name__

            def on_failure(event: Dict[str, Any]) -> None:
                logging.exception("Event %r failed due to exception %s", event, error_class_name, stack_info=True)

            retry_event(worker.queue_name, data, on_failure)

    return wrapper

def timer_expired(limit: int, event_count: int, signal: int, frame: FrameType) -> None:
    raise WorkerTimeoutException(limit, event_count)

class QueueProcessingWorker(ABC):
    queue_name: str
    MAX_CONSUME_SECONDS: Optional[int] = 30
    ENABLE_TIMEOUTS = False
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 50
    MAX_SECONDS_BEFORE_UPDATE_STATS = 30

    def __init__(self) -> None:
        self.q: Optional[SimpleQueueClient] = None
        if not hasattr(self, "queue_name"):
            raise WorkerDeclarationException("Queue worker declared without queue_name")

        self.initialize_statistics()

    def initialize_statistics(self) -> None:
        self.queue_last_emptied_timestamp = time.time()
        self.consumed_since_last_emptied = 0
        self.recent_consume_times: MutableSequence[Tuple[int, float]] = deque(maxlen=50)
        self.consume_iteration_counter = 0
        self.idle = True
        self.last_statistics_update_time = 0.0

        self.update_statistics(0)

    def update_statistics(self, remaining_local_queue_size: int) -> None:
        total_seconds = sum(seconds for _, seconds in self.recent_consume_times)
        total_events = sum(events_number for events_number, _ in self.recent_consume_times)
        if total_events == 0:
            recent_average_consume_time = None
        else:
            recent_average_consume_time = total_seconds / total_events
        stats_dict = dict(
            update_time=time.time(),
            recent_average_consume_time=recent_average_consume_time,
            current_queue_size=remaining_local_queue_size,
            queue_last_emptied_timestamp=self.queue_last_emptied_timestamp,
            consumed_since_last_emptied=self.consumed_since_last_emptied,
        )

        os.makedirs(settings.QUEUE_STATS_DIR, exist_ok=True)

        fname = f'{self.queue_name}.stats'
        fn = os.path.join(settings.QUEUE_STATS_DIR, fname)
        with lockfile(fn + '.lock'):
            tmp_fn = fn + '.tmp'
            with open(tmp_fn, 'wb') as f:
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

    def do_consume(self, consume_func: Callable[[List[Dict[str, Any]]], None],
                   events: List[Dict[str, Any]]) -> None:
        consume_time_seconds: Optional[float] = None
        with configure_scope() as scope:
            scope.clear_breadcrumbs()
            add_breadcrumb(
                type='debug',
                category='queue_processor',
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
                self.update_statistics(self.get_remaining_local_queue_size())

            time_start = time.time()
            if self.MAX_CONSUME_SECONDS and self.ENABLE_TIMEOUTS:
                try:
                    signal.signal(
                        signal.SIGALRM,
                        functools.partial(timer_expired, self.MAX_CONSUME_SECONDS, len(events)),
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
                self.update_statistics(0)
                self.idle = True
                return

            self.consume_iteration_counter += 1
            if (self.consume_iteration_counter >= self.CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM
                    or time.time() - self.last_statistics_update_time >= self.MAX_SECONDS_BEFORE_UPDATE_STATS):
                self.consume_iteration_counter = 0
                self.update_statistics(remaining_local_queue_size)

    def consume_single_event(self, event: Dict[str, Any]) -> None:
        consume_func = lambda events: self.consume(events[0])
        self.do_consume(consume_func, [event])

    def _handle_consume_exception(self, events: List[Dict[str, Any]], exception: Exception) -> None:
        with configure_scope() as scope:
            scope.set_context("events", {
                "data": events,
                "queue_name": self.queue_name,
            })
            if isinstance(exception, WorkerTimeoutException):
                with sentry_sdk.push_scope() as scope:
                    scope.fingerprint = ['worker-timeout', self.queue_name]
                    logging.exception("%s in queue %s",
                                      str(exception), self.queue_name, stack_info=True)
            else:
                logging.exception("Problem handling data on queue %s", self.queue_name, stack_info=True)
        if not os.path.exists(settings.QUEUE_ERROR_DIR):
            os.mkdir(settings.QUEUE_ERROR_DIR)  # nocoverage
        # Use 'mark_sanitized' to prevent Pysa from detecting this false positive
        # flow. 'queue_name' is always a constant string.
        fname = mark_sanitized(f'{self.queue_name}.errors')
        fn = os.path.join(settings.QUEUE_ERROR_DIR, fname)
        line = f'{time.asctime()}\t{orjson.dumps(events).decode()}\n'
        lock_fn = fn + '.lock'
        with lockfile(lock_fn):
            with open(fn, 'ab') as f:
                f.write(line.encode('utf-8'))
        check_and_send_restart_signal()

    def setup(self) -> None:
        self.q = SimpleQueueClient()

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

@assign_queue('signups')
class SignupWorker(QueueProcessingWorker):
    def consume(self, data: Dict[str, Any]) -> None:
        # TODO: This is the only implementation with Dict cf Mapping; should we simplify?
        user_profile = get_user_profile_by_id(data['user_id'])
        logging.info(
            "Processing signup for user %s in realm %s",
            user_profile.id, user_profile.realm.string_id,
        )
        if settings.MAILCHIMP_API_KEY and settings.PRODUCTION:
            endpoint = "https://{}.api.mailchimp.com/3.0/lists/{}/members".format(
                settings.MAILCHIMP_API_KEY.split('-')[1], settings.ZULIP_FRIENDS_LIST_ID,
            )
            params = dict(data)
            del params['user_id']
            params['list_id'] = settings.ZULIP_FRIENDS_LIST_ID
            params['status'] = 'subscribed'
            r = requests.post(endpoint, auth=('apikey', settings.MAILCHIMP_API_KEY), json=params, timeout=10)
            if r.status_code == 400 and orjson.loads(r.content)['title'] == 'Member Exists':
                logging.warning("Attempted to sign up already existing email to list: %s",
                                data['email_address'])
            elif r.status_code == 400:
                retry_event(self.queue_name, data, lambda e: r.raise_for_status())
            else:
                r.raise_for_status()

@assign_queue('invites')
class ConfirmationEmailWorker(QueueProcessingWorker):
    def consume(self, data: Mapping[str, Any]) -> None:
        if "email" in data:
            # When upgrading from a version up through 1.7.1, there may be
            # existing items in the queue with `email` instead of `prereg_id`.
            invitee = filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(email__iexact=data["email"].strip())
            ).latest("invited_at")
        else:
            invitee = filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(id=data["prereg_id"])
            ).first()
            if invitee is None:
                # The invitation could have been revoked
                return

        referrer = get_user_profile_by_id(data["referrer_id"])
        logger.info("Sending invitation for realm %s to %s", referrer.realm.string_id, invitee.email)
        activate_url = do_send_confirmation_email(invitee, referrer)

        # queue invitation reminder
        if settings.INVITATION_LINK_VALIDITY_DAYS >= 4:
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
                language=referrer.realm.default_language,
                context=context,
                delay=datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS - 2))

@assign_queue('user_activity')
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

            if "client_id" not in event:
                # This is for compatibility with older events still stuck in the queue,
                # that used the client name in event["client"] instead of having
                # event["client_id"] directly.
                # TODO: This can be deleted for release >= 4.0.
                if event["client"] not in self.client_id_map:
                    client = get_client(event["client"])
                    self.client_id_map[event["client"]] = client.id
                client_id = self.client_id_map[event["client"]]
            else:
                client_id = event["client_id"]

            key_tuple = (user_profile_id, client_id, event["query"])
            if key_tuple not in uncommitted_events:
                uncommitted_events[key_tuple] = (1, event['time'])
            else:
                count, time = uncommitted_events[key_tuple]
                uncommitted_events[key_tuple] = (count + 1, max(time, event['time']))

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

@assign_queue('user_activity_interval')
class UserActivityIntervalWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        log_time = timestamp_to_datetime(event["time"])
        do_update_user_activity_interval(user_profile, log_time)

@assign_queue('user_presence')
class UserPresenceWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.debug("Received presence event: %s", event)
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        status = event["status"]
        do_update_user_presence(user_profile, client, log_time, status)

@assign_queue('missedmessage_emails')
class MissedMessageWorker(QueueProcessingWorker):
    # Aggregate all messages received over the last BATCH_DURATION
    # seconds to let someone finish sending a batch of messages and/or
    # editing them before they are sent out as emails to recipients.
    #
    # The timer is running whenever; we poll at most every TIMER_FREQUENCY
    # seconds, to avoid excessive activity.
    #
    # TODO: Since this process keeps events in memory for up to 2
    # minutes, it now will lose approximately BATCH_DURATION worth of
    # missed_message emails whenever it is restarted as part of a
    # server restart.  We should probably add some sort of save/reload
    # mechanism for that case.
    TIMER_FREQUENCY = 5
    BATCH_DURATION = 120
    timer_event: Optional[Timer] = None
    events_by_recipient: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    batch_start_by_recipient: Dict[int, float] = {}

    # This lock protects access to all of the data structures declared
    # above.  A lock is required because maybe_send_batched_emails, as
    # the argument to Timer, runs in a separate thread from the rest
    # of the consumer.
    lock = Lock()

    def consume(self, event: Dict[str, Any]) -> None:
        with self.lock:
            logging.debug("Received missedmessage_emails event: %s", event)

            # When we process an event, just put it into the queue and ensure we have a timer going.
            user_profile_id = event['user_profile_id']
            if user_profile_id not in self.batch_start_by_recipient:
                self.batch_start_by_recipient[user_profile_id] = time.time()
            self.events_by_recipient[user_profile_id].append(event)

            self.ensure_timer()

    def ensure_timer(self) -> None:
        # The caller is responsible for ensuring self.lock is held when it calls this.
        if self.timer_event is not None:
            return

        self.timer_event = Timer(self.TIMER_FREQUENCY, MissedMessageWorker.maybe_send_batched_emails,
                                 [self])
        self.timer_event.start()

    def maybe_send_batched_emails(self) -> None:
        with self.lock:
            # self.timer_event just triggered execution of this
            # function in a thread, so now that we hold the lock, we
            # clear the timer_event attribute to record that no Timer
            # is active.
            self.timer_event = None

            current_time = time.time()
            for user_profile_id, timestamp in list(self.batch_start_by_recipient.items()):
                if current_time - timestamp < self.BATCH_DURATION:
                    continue
                events = self.events_by_recipient[user_profile_id]
                logging.info("Batch-processing %s missedmessage_emails events for user %s",
                             len(events), user_profile_id)
                handle_missedmessage_emails(user_profile_id, events)
                del self.events_by_recipient[user_profile_id]
                del self.batch_start_by_recipient[user_profile_id]

            # By only restarting the timer if there are actually events in
            # the queue, we ensure this queue processor is idle when there
            # are no missed-message emails to process.  This avoids
            # constant CPU usage when there is no work to do.
            if len(self.batch_start_by_recipient) > 0:
                self.ensure_timer()

@assign_queue('email_senders')
class EmailSendingWorker(QueueProcessingWorker):
    @retry_send_email_failures
    def consume(self, event: Dict[str, Any]) -> None:
        # Copy the event, so that we don't pass the `failed_tries'
        # data to send_email_from_dict (which neither takes that
        # argument nor needs that data).
        copied_event = copy.deepcopy(event)
        if 'failed_tries' in copied_event:
            del copied_event['failed_tries']
        handle_send_email_format_changes(copied_event)
        send_email_from_dict(copied_event)

@assign_queue('missedmessage_mobile_notifications')
class PushNotificationsWorker(QueueProcessingWorker):  # nocoverage
    def start(self) -> None:
        # initialize_push_notifications doesn't strictly do anything
        # beyond printing some logging warnings if push notifications
        # are not available in the current configuration.
        initialize_push_notifications()
        super().start()

    def consume(self, event: Dict[str, Any]) -> None:
        try:
            if event.get("type", "add") == "remove":
                message_ids = event.get('message_ids')
                if message_ids is None:  # legacy task across an upgrade
                    message_ids = [event['message_id']]
                handle_remove_push_notification(event['user_profile_id'], message_ids)
            else:
                handle_push_notification(event['user_profile_id'], event)
        except PushNotificationBouncerRetryLaterError:
            def failure_processor(event: Dict[str, Any]) -> None:
                logger.warning(
                    "Maximum retries exceeded for trigger:%s event:push_notification",
                    event['user_profile_id'])
            retry_event(self.queue_name, event, failure_processor)

@assign_queue('error_reports')
class ErrorReporter(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.info("Processing traceback with type %s for %s", event['type'], event.get('user_email'))
        if settings.ERROR_REPORTING:
            do_report_error(event['report']['host'], event['type'], event['report'])

@assign_queue('digest_emails')
class DigestWorker(QueueProcessingWorker):  # nocoverage
    # Who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.info("Received digest event: %s", event)
        handle_digest_email(event["user_profile_id"], event["cutoff"])

@assign_queue('email_mirror')
class MirrorWorker(QueueProcessingWorker):
    def consume(self, event: Mapping[str, Any]) -> None:
        rcpt_to = event['rcpt_to']
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
            except RateLimited:
                logger.warning("MirrorWorker: Rejecting an email from: %s "
                               "to realm: %s - rate limited.",
                               msg['From'], recipient_realm.name)
                return

        mirror_email(msg, rcpt_to=rcpt_to)

@assign_queue('embed_links')
class FetchLinksEmbedData(QueueProcessingWorker):
    # This is a slow queue with network requests, so a disk write is negligible.
    # Update stats file after every consume call.
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 1

    def consume(self, event: Mapping[str, Any]) -> None:
        for url in event['urls']:
            start_time = time.time()
            url_preview.get_link_embed_data(url)
            logging.info("Time spent on get_link_embed_data for %s: %s", url, time.time() - start_time)

        message = Message.objects.get(id=event['message_id'])
        # If the message changed, we will run this task after updating the message
        # in zerver.views.message_edit.update_message_backend
        if message.content != event['message_content']:
            return
        if message.content is not None:
            query = UserMessage.objects.filter(
                message=message.id,
            )
            message_user_ids = set(query.values_list('user_profile_id', flat=True))

            # Fetch the realm whose settings we're using for rendering
            realm = Realm.objects.get(id=event['message_realm_id'])

            # If rendering fails, the called code will raise a JsonableError.
            rendered_content = render_incoming_message(
                message,
                message.content,
                message_user_ids,
                realm)
            do_update_embedded_data(
                message.sender, message, message.content, rendered_content)

@assign_queue('outgoing_webhooks')
class OutgoingWebhookWorker(QueueProcessingWorker):
    def consume(self, event: Dict[str, Any]) -> None:
        message = event['message']
        event['command'] = message['content']

        services = get_bot_services(event['user_profile_id'])
        for service in services:
            event['service_name'] = str(service.name)
            service_handler = get_outgoing_webhook_service_handler(service)
            request_data = service_handler.build_bot_request(event)
            if request_data:
                do_rest_call(service.base_url,
                             request_data,
                             event,
                             service_handler)

@assign_queue('embedded_bots')
class EmbeddedBotWorker(QueueProcessingWorker):

    def get_bot_api_client(self, user_profile: UserProfile) -> EmbeddedBotHandler:
        return EmbeddedBotHandler(user_profile)

    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile_id = event['user_profile_id']
        user_profile = get_user_profile_by_id(user_profile_id)

        message: Dict[str, Any] = event['message']

        # TODO: Do we actually want to allow multiple Services per bot user?
        services = get_bot_services(user_profile_id)
        for service in services:
            bot_handler = get_bot_handler(str(service.name))
            if bot_handler is None:
                logging.error(
                    "Error: User %s has bot with invalid embedded bot service %s",
                    user_profile_id, service.name,
                )
                continue
            try:
                if hasattr(bot_handler, 'initialize'):
                    bot_handler.initialize(self.get_bot_api_client(user_profile))
                if event['trigger'] == 'mention':
                    message['content'] = extract_query_without_mention(
                        message=message,
                        client=cast(ExternalBotHandler, self.get_bot_api_client(user_profile)),
                    )
                    assert message['content'] is not None
                bot_handler.handle_message(
                    message=message,
                    bot_handler=self.get_bot_api_client(user_profile),
                )
            except EmbeddedBotQuitException as e:
                logging.warning(str(e))

@assign_queue('deferred_work')
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
        if event['type'] == 'mark_stream_messages_as_read':
            user_profile = get_user_profile_by_id(event['user_profile_id'])

            for recipient_id in event['stream_recipient_ids']:
                do_mark_stream_messages_as_read(user_profile, recipient_id)
        elif event["type"] == 'mark_stream_messages_as_read_for_everyone':
            # This event is generated by the stream deactivation code path.
            batch_size = 100
            offset = 0
            while True:
                messages = Message.objects.filter(recipient_id=event["stream_recipient_id"]) \
                    .order_by("id")[offset:offset + batch_size]
                UserMessage.objects.filter(message__in=messages).extra(where=[UserMessage.where_unread()]) \
                    .update(flags=F('flags').bitor(UserMessage.flags.read))
                offset += len(messages)
                if len(messages) < batch_size:
                    break
        elif event['type'] == 'clear_push_device_tokens':
            try:
                clear_push_device_tokens(event["user_profile_id"])
            except PushNotificationBouncerRetryLaterError:
                def failure_processor(event: Dict[str, Any]) -> None:
                    logger.warning(
                        "Maximum retries exceeded for trigger:%s event:clear_push_device_tokens",
                        event['user_profile_id'])
                retry_event(self.queue_name, event, failure_processor)
        elif event['type'] == 'realm_export':
            start = time.time()
            realm = Realm.objects.get(id=event['realm_id'])
            output_dir = tempfile.mkdtemp(prefix="zulip-export-")
            export_event = RealmAuditLog.objects.get(id=event['id'])
            user_profile = get_user_profile_by_id(event['user_profile_id'])

            try:
                public_url = export_realm_wrapper(realm=realm, output_dir=output_dir,
                                                  threads=6, upload=True, public_only=True,
                                                  delete_after_upload=True)
            except Exception:
                export_event.extra_data = orjson.dumps(dict(
                    failed_timestamp=timezone_now().timestamp(),
                )).decode()
                export_event.save(update_fields=['extra_data'])
                logging.error(
                    "Data export for %s failed after %s",
                    user_profile.realm.string_id, time.time() - start,
                )
                notify_realm_export(user_profile)
                return

            assert public_url is not None

            # Update the extra_data field now that the export is complete.
            export_event.extra_data = orjson.dumps(dict(
                export_path=urllib.parse.urlparse(public_url).path,
            )).decode()
            export_event.save(update_fields=['extra_data'])

            # Send a private message notification letting the user who
            # triggered the export know the export finished.
            with override_language(user_profile.default_language):
                content = _("Your data export is complete and has been uploaded here:\n\n{public_url}").format(public_url=public_url)
            internal_send_private_message(
                realm=user_profile.realm,
                sender=get_system_bot(settings.NOTIFICATION_BOT),
                recipient_user=user_profile,
                content=content,
            )

            # For future frontend use, also notify administrator
            # clients that the export happened.
            notify_realm_export(user_profile)
            logging.info(
                "Completed data export for %s in %s",
                user_profile.realm.string_id, time.time() - start,
            )

@assign_queue('test', is_test_queue=True)
class TestWorker(QueueProcessingWorker):
    # This worker allows you to test the queue worker infrastructure without
    # creating significant side effects.  It can be useful in development or
    # for troubleshooting prod/staging.  It pulls a message off the test queue
    # and appends it to a file in /tmp.
    def consume(self, event: Mapping[str, Any]) -> None:  # nocoverage
        fn = settings.ZULIP_WORKER_TEST_FILE
        message = orjson.dumps(event)
        logging.info("TestWorker should append this message to %s: %s", fn, message.decode())
        with open(fn, 'ab') as f:
            f.write(message + b'\n')

@assign_queue('noop', is_test_queue=True)
class NoopWorker(QueueProcessingWorker):
    """Used to profile the queue processing framework, in zilencer's queue_rate."""

    def __init__(self, max_consume: int=1000, slow_queries: Optional[List[int]]=None) -> None:
        self.consumed = 0
        self.max_consume = max_consume
        self.slow_queries: Set[int] = set(slow_queries or [])

    def consume(self, event: Mapping[str, Any]) -> None:
        self.consumed += 1
        if self.consumed in self.slow_queries:
            logging.info("Slow request...")
            time.sleep(60)
            logging.info("Done!")
        if self.consumed >= self.max_consume:
            self.stop()

@assign_queue('noop_batch', is_test_queue=True)
class BatchNoopWorker(LoopQueueProcessingWorker):
    """Used to profile the queue processing framework, in zilencer's queue_rate."""
    batch_size = 500

    def __init__(self, max_consume: int=1000, slow_queries: Optional[List[int]]=None) -> None:
        self.consumed = 0
        self.max_consume = max_consume
        self.slow_queries: Set[int] = set(slow_queries or [])

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
