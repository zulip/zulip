import base64
import os
import smtplib
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional
from unittest.mock import MagicMock, patch

import orjson
from django.conf import settings
from django.test import override_settings

from zerver.lib.email_mirror import RateLimitedRealmMirror
from zerver.lib.email_mirror_helpers import encode_email_address
from zerver.lib.queue import MAX_REQUEST_RETRIES
from zerver.lib.rate_limiter import RateLimiterLockingException
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish, simulated_queue_client
from zerver.models import PreregistrationUser, UserActivity, get_client, get_realm, get_stream
from zerver.tornado.event_queue import build_offline_notification
from zerver.worker import queue_processors
from zerver.worker.queue_processors import (
    EmailSendingWorker,
    LoopQueueProcessingWorker,
    MissedMessageWorker,
    QueueProcessingWorker,
    WorkerTimeoutException,
    get_active_worker_queues,
)

Event = Dict[str, Any]

# This is used for testing LoopQueueProcessingWorker, which
# would run forever if we don't mock time.sleep to abort the
# loop.
class AbortLoop(Exception):
    pass

loopworker_sleep_mock = patch(
    'zerver.worker.queue_processors.time.sleep',
    side_effect=AbortLoop,
)

class WorkerTest(ZulipTestCase):
    class FakeClient:
        def __init__(self) -> None:
            self.consumers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
            self.queues: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        def enqueue(self, queue_name: str, data: Dict[str, Any]) -> None:
            self.queues[queue_name].append(data)

        def register_json_consumer(self,
                                   queue_name: str,
                                   callback: Callable[[Dict[str, Any]], None]) -> None:
            self.consumers[queue_name] = callback

        def start_consuming(self) -> None:
            for queue_name in self.queues.keys():
                callback = self.consumers[queue_name]
                for data in self.queues[queue_name]:
                    callback(data)
                self.queues[queue_name] = []

        @contextmanager
        def json_drain_queue(self, queue_name: str) -> Iterator[List[Event]]:
            events = self.queues[queue_name]
            self.queues[queue_name] = []
            yield events

        def local_queue_size(self) -> int:
            return sum([len(q) for q in self.queues.values()])

    def test_UserActivityWorker(self) -> None:
        fake_client = self.FakeClient()

        user = self.example_user('hamlet')
        UserActivity.objects.filter(
            user_profile = user.id,
            client = get_client('ios'),
        ).delete()

        data = dict(
            user_profile_id = user.id,
            client_id = get_client('ios').id,
            time = time.time(),
            query = 'send_message',
        )
        fake_client.enqueue('user_activity', data)

        # The block below adds an event using the old format,
        # having the client name instead of id, to test the queue
        # worker handles it correctly. That compatibility code can
        # be deleted in a later release, and this test should then be cleaned up.
        data_old_format = dict(
            user_profile_id = user.id,
            client = 'ios',
            time = time.time(),
            query = 'send_message',
        )
        fake_client.enqueue('user_activity', data_old_format)

        with loopworker_sleep_mock:
            with simulated_queue_client(lambda: fake_client):
                worker = queue_processors.UserActivityWorker()
                worker.setup()
                try:
                    worker.start()
                except AbortLoop:
                    pass
                activity_records = UserActivity.objects.filter(
                    user_profile = user.id,
                    client = get_client('ios'),
                )
                self.assertEqual(len(activity_records), 1)
                self.assertEqual(activity_records[0].count, 2)

        # Now process the event a second time and confirm count goes
        # up. Ideally, we'd use an event with a slightly newer
        # time, but it's not really important.
        fake_client.enqueue('user_activity', data)
        with loopworker_sleep_mock:
            with simulated_queue_client(lambda: fake_client):
                worker = queue_processors.UserActivityWorker()
                worker.setup()
                try:
                    worker.start()
                except AbortLoop:
                    pass
                activity_records = UserActivity.objects.filter(
                    user_profile = user.id,
                    client = get_client('ios'),
                )
                self.assertEqual(len(activity_records), 1)
                self.assertEqual(activity_records[0].count, 3)

    def test_missed_message_worker(self) -> None:
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')

        hamlet1_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=hamlet,
            content='hi hamlet',
        )

        hamlet2_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=hamlet,
            content='goodbye hamlet',
        )

        hamlet3_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=hamlet,
            content='hello again hamlet',
        )

        othello_msg_id = self.send_personal_message(
            from_user=cordelia,
            to_user=othello,
            content='where art thou, othello?',
        )

        events = [
            dict(user_profile_id=hamlet.id, message_id=hamlet1_msg_id),
            dict(user_profile_id=hamlet.id, message_id=hamlet2_msg_id),
            dict(user_profile_id=othello.id, message_id=othello_msg_id),
        ]

        fake_client = self.FakeClient()
        for event in events:
            fake_client.enqueue('missedmessage_emails', event)

        mmw = MissedMessageWorker()

        class MockTimer():
            is_running = False

            def is_alive(self) -> bool:
                return self.is_running

            def start(self) -> None:
                self.is_running = True

        timer = MockTimer()
        loopworker_sleep_mock = patch(
            'zerver.worker.queue_processors.Timer',
            return_value=timer,
        )

        send_mock = patch(
            'zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip',
        )
        mmw.BATCH_DURATION = 0

        bonus_event = dict(user_profile_id=hamlet.id, message_id=hamlet3_msg_id)

        with send_mock as sm, loopworker_sleep_mock as tm:
            with simulated_queue_client(lambda: fake_client):
                self.assertFalse(timer.is_alive())
                mmw.setup()
                mmw.start()
                self.assertTrue(timer.is_alive())
                fake_client.enqueue('missedmessage_emails', bonus_event)

                # Double-calling start is our way to get it to run again
                self.assertTrue(timer.is_alive())
                mmw.start()
                with self.assertLogs(level='INFO') as info_logs:
                    # Now, we actually send the emails.
                    mmw.maybe_send_batched_emails()
                self.assertEqual(info_logs.output, [
                    'INFO:root:Batch-processing 3 missedmessage_emails events for user 10',
                    'INFO:root:Batch-processing 1 missedmessage_emails events for user 12'
                ])

                self.assertEqual(mmw.timer_event, None)

        self.assertEqual(tm.call_args[0][0], 5)  # should sleep 5 seconds

        args = [c[0] for c in sm.call_args_list]
        arg_dict = {
            arg[0].id: dict(
                missed_messages=arg[1],
                count=arg[2],
            )
            for arg in args
        }

        hamlet_info = arg_dict[hamlet.id]
        self.assertEqual(hamlet_info['count'], 3)
        self.assertEqual(
            {m['message'].content for m in hamlet_info['missed_messages']},
            {'hi hamlet', 'goodbye hamlet', 'hello again hamlet'},
        )

        othello_info = arg_dict[othello.id]
        self.assertEqual(othello_info['count'], 1)
        self.assertEqual(
            {m['message'].content for m in othello_info['missed_messages']},
            {'where art thou, othello?'},
        )

    def test_push_notifications_worker(self) -> None:
        """
        The push notifications system has its own comprehensive test suite,
        so we can limit ourselves to simple unit testing the queue processor,
        without going deeper into the system - by mocking the handle_push_notification
        functions to immediately produce the effect we want, to test its handling by the queue
        processor.
        """
        fake_client = self.FakeClient()

        def fake_publish(queue_name: str,
                         event: Dict[str, Any],
                         processor: Callable[[Any], None]) -> None:
            fake_client.enqueue(queue_name, event)

        def generate_new_message_notification() -> Dict[str, Any]:
            return build_offline_notification(1, 1)

        def generate_remove_notification() -> Dict[str, Any]:
            return {
                "type": "remove",
                "user_profile_id": 1,
                "message_ids": [1],
            }

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.PushNotificationsWorker()
            worker.setup()
            with patch('zerver.worker.queue_processors.handle_push_notification') as mock_handle_new, \
                    patch('zerver.worker.queue_processors.handle_remove_push_notification') as mock_handle_remove, \
                    patch('zerver.worker.queue_processors.initialize_push_notifications'):
                event_new = generate_new_message_notification()
                event_remove = generate_remove_notification()
                fake_client.enqueue('missedmessage_mobile_notifications', event_new)
                fake_client.enqueue('missedmessage_mobile_notifications', event_remove)

                worker.start()
                mock_handle_new.assert_called_once_with(event_new['user_profile_id'], event_new)
                mock_handle_remove.assert_called_once_with(event_remove['user_profile_id'],
                                                           event_remove['message_ids'])

            with patch('zerver.worker.queue_processors.handle_push_notification',
                       side_effect=PushNotificationBouncerRetryLaterError("test")) as mock_handle_new, \
                    patch('zerver.worker.queue_processors.handle_remove_push_notification',
                          side_effect=PushNotificationBouncerRetryLaterError("test")) as mock_handle_remove, \
                    patch('zerver.worker.queue_processors.initialize_push_notifications'):
                event_new = generate_new_message_notification()
                event_remove = generate_remove_notification()
                fake_client.enqueue('missedmessage_mobile_notifications', event_new)
                fake_client.enqueue('missedmessage_mobile_notifications', event_remove)

                with mock_queue_publish('zerver.lib.queue.queue_json_publish', side_effect=fake_publish), \
                        self.assertLogs('zerver.worker.queue_processors', 'WARNING') as warn_logs:
                    worker.start()
                    self.assertEqual(mock_handle_new.call_count, 1 + MAX_REQUEST_RETRIES)
                    self.assertEqual(mock_handle_remove.call_count, 1 + MAX_REQUEST_RETRIES)
                self.assertEqual(warn_logs.output, [
                    'WARNING:zerver.worker.queue_processors:Maximum retries exceeded for trigger:1 event:push_notification',
                ] * 2)

    @patch('zerver.worker.queue_processors.mirror_email')
    def test_mirror_worker(self, mock_mirror_email: MagicMock) -> None:
        fake_client = self.FakeClient()
        stream = get_stream('Denmark', get_realm('zulip'))
        stream_to_address = encode_email_address(stream)
        data = [
            dict(
                msg_base64=base64.b64encode(b'\xf3test').decode(),
                time=time.time(),
                rcpt_to=stream_to_address,
            ),
        ] * 3
        for element in data:
            fake_client.enqueue('email_mirror', element)

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.MirrorWorker()
            worker.setup()
            worker.start()

        self.assertEqual(mock_mirror_email.call_count, 3)

    @patch('zerver.lib.rate_limiter.logger.warning')
    @patch('zerver.worker.queue_processors.mirror_email')
    @override_settings(RATE_LIMITING_MIRROR_REALM_RULES=[(10, 2)])
    def test_mirror_worker_rate_limiting(self, mock_mirror_email: MagicMock,
                                         mock_warn: MagicMock) -> None:
        fake_client = self.FakeClient()
        realm = get_realm('zulip')
        RateLimitedRealmMirror(realm).clear_history()
        stream = get_stream('Denmark', realm)
        stream_to_address = encode_email_address(stream)
        data = [
            dict(
                msg_base64=base64.b64encode(b'\xf3test').decode(),
                time=time.time(),
                rcpt_to=stream_to_address,
            ),
        ] * 5
        for element in data:
            fake_client.enqueue('email_mirror', element)

        with simulated_queue_client(lambda: fake_client), \
                self.assertLogs('zerver.worker.queue_processors', level='WARNING') as warn_logs:
            start_time = time.time()
            with patch('time.time', return_value=start_time):
                worker = queue_processors.MirrorWorker()
                worker.setup()
                worker.start()
                # Of the first 5 messages, only 2 should be processed
                # (the rest being rate-limited):
                self.assertEqual(mock_mirror_email.call_count, 2)

                # If a new message is sent into the stream mirror, it will get rejected:
                fake_client.enqueue('email_mirror', data[0])
                worker.start()
                self.assertEqual(mock_mirror_email.call_count, 2)

                # However, missed message emails don't get rate limited:
                with self.settings(EMAIL_GATEWAY_PATTERN="%s@example.com"):
                    address = 'mm' + ('x' * 32) + '@example.com'
                    event = dict(
                        msg_base64=base64.b64encode(b'\xf3test').decode(),
                        time=time.time(),
                        rcpt_to=address,
                    )
                    fake_client.enqueue('email_mirror', event)
                    worker.start()
                    self.assertEqual(mock_mirror_email.call_count, 3)

            # After some times passes, emails get accepted again:
            with patch('time.time', return_value=(start_time + 11.0)):
                fake_client.enqueue('email_mirror', data[0])
                worker.start()
                self.assertEqual(mock_mirror_email.call_count, 4)

                # If RateLimiterLockingException is thrown, we rate-limit the new message:
                with patch('zerver.lib.rate_limiter.RedisRateLimiterBackend.incr_ratelimit',
                           side_effect=RateLimiterLockingException):
                    fake_client.enqueue('email_mirror', data[0])
                    worker.start()
                    self.assertEqual(mock_mirror_email.call_count, 4)
                    mock_warn.assert_called_with(
                        "Deadlock trying to incr_ratelimit for %s",
                        f"RateLimitedRealmMirror:{realm.string_id}",
                    )
        self.assertEqual(warn_logs.output, [
            'WARNING:zerver.worker.queue_processors:MirrorWorker: Rejecting an email from: None to realm: Zulip Dev - rate limited.'
        ] * 5)

    def test_email_sending_worker_retries(self) -> None:
        """Tests the retry_send_email_failures decorator to make sure it
        retries sending the email 3 times and then gives up."""
        fake_client = self.FakeClient()

        data = {
            'template_prefix': 'zerver/emails/confirm_new_email',
            'to_emails': [self.example_email("hamlet")],
            'from_name': 'Zulip Account Security',
            'from_address': FromAddress.NOREPLY,
            'context': {},
        }
        fake_client.enqueue('email_senders', data)

        def fake_publish(queue_name: str,
                         event: Dict[str, Any],
                         processor: Optional[Callable[[Any], None]]) -> None:
            fake_client.enqueue(queue_name, event)

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.EmailSendingWorker()
            worker.setup()
            with patch('zerver.lib.send_email.build_email',
                       side_effect=smtplib.SMTPServerDisconnected), \
                    mock_queue_publish('zerver.lib.queue.queue_json_publish',
                                       side_effect=fake_publish), \
                    patch('logging.exception'):
                worker.start()

        self.assertEqual(data['failed_tries'], 1 + MAX_REQUEST_RETRIES)

    def test_signups_worker_retries(self) -> None:
        """Tests the retry logic of signups queue."""
        fake_client = self.FakeClient()

        user_id = self.example_user('hamlet').id
        data = {'user_id': user_id, 'id': 'test_missed'}
        fake_client.enqueue('signups', data)

        def fake_publish(queue_name: str, event: Dict[str, Any], processor: Optional[Callable[[Any], None]]) -> None:
            fake_client.enqueue(queue_name, event)

        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.content = orjson.dumps({'title': ''})
        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.SignupWorker()
            worker.setup()
            with patch('zerver.worker.queue_processors.requests.post',
                       return_value=fake_response), \
                    mock_queue_publish('zerver.lib.queue.queue_json_publish',
                                       side_effect=fake_publish), \
                    patch('logging.info'), \
                    self.settings(MAILCHIMP_API_KEY='one-two',
                                  PRODUCTION=True,
                                  ZULIP_FRIENDS_LIST_ID='id'):
                worker.start()

        self.assertEqual(data['failed_tries'], 1 + MAX_REQUEST_RETRIES)

    def test_signups_worker_existing_member(self) -> None:
        fake_client = self.FakeClient()

        user_id = self.example_user('hamlet').id
        data = {'user_id': user_id,
                'id': 'test_missed',
                'email_address': 'foo@bar.baz'}
        fake_client.enqueue('signups', data)

        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.content = orjson.dumps({'title': 'Member Exists'})
        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.SignupWorker()
            worker.setup()
            with patch('zerver.worker.queue_processors.requests.post',
                       return_value=fake_response), \
                    self.settings(MAILCHIMP_API_KEY='one-two',
                                  PRODUCTION=True,
                                  ZULIP_FRIENDS_LIST_ID='id'), \
                    self.assertLogs(level='INFO') as info_logs:
                with patch('logging.warning') as logging_warning_mock:
                    worker.start()
                    logging_warning_mock.assert_called_once_with(
                        "Attempted to sign up already existing email to list: %s",
                        "foo@bar.baz",
                    )
            self.assertEqual(info_logs.output, [
                'INFO:root:Processing signup for user 10 in realm zulip'
            ])

    def test_signups_bad_request(self) -> None:
        fake_client = self.FakeClient()

        user_id = self.example_user('hamlet').id
        data = {'user_id': user_id, 'id': 'test_missed'}
        fake_client.enqueue('signups', data)

        fake_response = MagicMock()
        fake_response.status_code = 444  # Any non-400 bad request code.
        fake_response.content = orjson.dumps({'title': 'Member Exists'})
        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.SignupWorker()
            worker.setup()
            with patch('zerver.worker.queue_processors.requests.post',
                       return_value=fake_response), \
                    self.settings(MAILCHIMP_API_KEY='one-two',
                                  PRODUCTION=True,
                                  ZULIP_FRIENDS_LIST_ID='id'), \
                    self.assertLogs(level='INFO') as info_logs:
                worker.start()
                fake_response.raise_for_status.assert_called_once()
            self.assertEqual(info_logs.output, [
                'INFO:root:Processing signup for user 10 in realm zulip'
            ])

    def test_invites_worker(self) -> None:
        fake_client = self.FakeClient()
        inviter = self.example_user('iago')
        prereg_alice = PreregistrationUser.objects.create(
            email=self.nonreg_email('alice'), referred_by=inviter, realm=inviter.realm)
        PreregistrationUser.objects.create(
            email=self.nonreg_email('bob'), referred_by=inviter, realm=inviter.realm)
        data: List[Dict[str, Any]] = [
            dict(prereg_id=prereg_alice.id, referrer_id=inviter.id, email_body=None),
            # Nonexistent prereg_id, as if the invitation was deleted
            dict(prereg_id=-1, referrer_id=inviter.id, email_body=None),
            # Form with `email` is from versions up to Zulip 1.7.1
            dict(email=self.nonreg_email('bob'), referrer_id=inviter.id, email_body=None),
        ]
        for element in data:
            fake_client.enqueue('invites', element)

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.ConfirmationEmailWorker()
            worker.setup()
            with patch('zerver.lib.actions.send_email'), \
                    patch('zerver.worker.queue_processors.send_future_email') \
                    as send_mock, \
                    patch('logging.info'):
                worker.start()
                self.assertEqual(send_mock.call_count, 2)

    def test_error_handling(self) -> None:
        processed = []

        @queue_processors.assign_queue('unreliable_worker')
        class UnreliableWorker(queue_processors.QueueProcessingWorker):
            def consume(self, data: Mapping[str, Any]) -> None:
                if data["type"] == 'unexpected behaviour':
                    raise Exception('Worker task not performing as expected!')
                processed.append(data["type"])

        fake_client = self.FakeClient()
        for msg in ['good', 'fine', 'unexpected behaviour', 'back to normal']:
            fake_client.enqueue('unreliable_worker', {'type': msg})

        fn = os.path.join(settings.QUEUE_ERROR_DIR, 'unreliable_worker.errors')
        try:
            os.remove(fn)
        except OSError:  # nocoverage # error handling for the directory not existing
            pass

        with simulated_queue_client(lambda: fake_client):
            worker = UnreliableWorker()
            worker.setup()
            with patch('logging.exception') as logging_exception_mock:
                worker.start()
                logging_exception_mock.assert_called_once_with(
                    "Problem handling data on queue %s", "unreliable_worker",
                    stack_info=True,
                )

        self.assertEqual(processed, ['good', 'fine', 'back to normal'])
        with open(fn) as f:
            line = f.readline().strip()
        events = orjson.loads(line.split('\t')[1])
        self.assert_length(events, 1)
        event = events[0]
        self.assertEqual(event["type"], 'unexpected behaviour')

        processed = []

        @queue_processors.assign_queue('unreliable_loopworker')
        class UnreliableLoopWorker(queue_processors.LoopQueueProcessingWorker):
            def consume_batch(self, events: List[Dict[str, Any]]) -> None:
                for event in events:
                    if event["type"] == 'unexpected behaviour':
                        raise Exception('Worker task not performing as expected!')
                    processed.append(event["type"])

        for msg in ['good', 'fine', 'unexpected behaviour', 'back to normal']:
            fake_client.enqueue('unreliable_loopworker', {'type': msg})

        fn = os.path.join(settings.QUEUE_ERROR_DIR, 'unreliable_loopworker.errors')
        try:
            os.remove(fn)
        except OSError:  # nocoverage # error handling for the directory not existing
            pass

        with loopworker_sleep_mock, simulated_queue_client(lambda: fake_client):
            loopworker = UnreliableLoopWorker()
            loopworker.setup()
            with patch('logging.exception') as logging_exception_mock:
                try:
                    loopworker.start()
                except AbortLoop:
                    pass
                logging_exception_mock.assert_called_once_with(
                    "Problem handling data on queue %s", "unreliable_loopworker",
                    stack_info=True,
                )

        self.assertEqual(processed, ['good', 'fine'])
        with open(fn) as f:
            line = f.readline().strip()
        events = orjson.loads(line.split('\t')[1])
        self.assert_length(events, 4)

        self.assertEqual([event["type"] for event in events],
                         ['good', 'fine', 'unexpected behaviour', 'back to normal'])

    def test_timeouts(self) -> None:
        processed = []

        @queue_processors.assign_queue('timeout_worker')
        class TimeoutWorker(queue_processors.QueueProcessingWorker):
            MAX_CONSUME_SECONDS = 1

            def consume(self, data: Mapping[str, Any]) -> None:
                if data["type"] == 'timeout':
                    time.sleep(5)
                processed.append(data["type"])

        fake_client = self.FakeClient()
        for msg in ['good', 'fine', 'timeout', 'back to normal']:
            fake_client.enqueue('timeout_worker', {'type': msg})

        fn = os.path.join(settings.QUEUE_ERROR_DIR, 'timeout_worker.errors')
        try:
            os.remove(fn)
        except OSError:  # nocoverage # error handling for the directory not existing
            pass

        with simulated_queue_client(lambda: fake_client):
            worker = TimeoutWorker()
            worker.setup()
            worker.ENABLE_TIMEOUTS = True
            with patch('logging.exception') as logging_exception_mock:
                worker.start()
                logging_exception_mock.assert_called_once_with(
                    "%s in queue %s", str(WorkerTimeoutException(1, 1)), "timeout_worker",
                    stack_info=True,
                )

        self.assertEqual(processed, ['good', 'fine', 'back to normal'])
        with open(fn) as f:
            line = f.readline().strip()
        events = orjson.loads(line.split('\t')[1])
        self.assert_length(events, 1)
        event = events[0]
        self.assertEqual(event["type"], 'timeout')

    def test_worker_noname(self) -> None:
        class TestWorker(queue_processors.QueueProcessingWorker):
            def __init__(self) -> None:
                super().__init__()

            def consume(self, data: Mapping[str, Any]) -> None:
                pass  # nocoverage # this is intentionally not called
        with self.assertRaises(queue_processors.WorkerDeclarationException):
            TestWorker()

    def test_get_active_worker_queues(self) -> None:
        test_queue_count = len(get_active_worker_queues(queue_type='test'))
        self.assertEqual(3, test_queue_count)

        worker_queue_count = (len(QueueProcessingWorker.__subclasses__()) +
                              len(EmailSendingWorker.__subclasses__()) +
                              len(LoopQueueProcessingWorker.__subclasses__()) - 1)
        self.assertEqual(worker_queue_count, len(get_active_worker_queues()))
