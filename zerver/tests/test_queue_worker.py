
import os
import time
import ujson
import smtplib

from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase
from mock import patch, MagicMock
from typing import Any, Callable, Dict, List, Mapping, Tuple

from zerver.lib.test_helpers import simulated_queue_client
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_client, UserActivity
from zerver.worker import queue_processors

class WorkerTest(ZulipTestCase):
    class FakeClient(object):
        def __init__(self):
            # type: () -> None
            self.consumers = {}  # type: Dict[str, Callable]
            self.queue = []  # type: List[Tuple[str, Dict[str, Any]]]

        def register_json_consumer(self, queue_name, callback):
            # type: (str, Callable) -> None
            self.consumers[queue_name] = callback

        def start_consuming(self):
            # type: () -> None
            for queue_name, data in self.queue:
                callback = self.consumers[queue_name]
                callback(data)

    def test_mirror_worker(self):
        # type: () -> None
        fake_client = self.FakeClient()
        data = [
            dict(
                message=u'\xf3test',
                time=time.time(),
                rcpt_to=self.example_email('hamlet'),
            ),
            dict(
                message='\xf3test',
                time=time.time(),
                rcpt_to=self.example_email('hamlet'),
            ),
            dict(
                message='test',
                time=time.time(),
                rcpt_to=self.example_email('hamlet'),
            ),
        ]
        for element in data:
            fake_client.queue.append(('email_mirror', element))

        with patch('zerver.worker.queue_processors.mirror_email'):
            with simulated_queue_client(lambda: fake_client):
                worker = queue_processors.MirrorWorker()
                worker.setup()
                worker.start()

    def test_email_sending_worker_retries(self):
        # type: () -> None
        """Tests the retry_send_email_failures decorator to make sure it
        retries sending the email 3 times and then gives up."""
        fake_client = self.FakeClient()

        data = {'test': 'test', 'failed_tries': 0, 'id': 'test_missed'}
        fake_client.queue.append(('missedmessage_email_senders', data))

        def fake_publish(queue_name, event, processor):
            # type: (str, Dict[str, Any], Callable[[Any], None]) -> None
            fake_client.queue.append((queue_name, event))

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.MissedMessageSendingWorker()
            worker.setup()
            with patch('zerver.worker.queue_processors.send_email_from_dict',
                       side_effect=smtplib.SMTPServerDisconnected), \
                    patch('zerver.lib.queue.queue_json_publish',
                          side_effect=fake_publish), \
                    patch('logging.exception'):
                worker.start()

        self.assertEqual(data['failed_tries'], 4)

    def test_signups_worker_retries(self):
        # type: () -> None
        """Tests the retry logic of signups queue."""
        fake_client = self.FakeClient()

        user_id = self.example_user('hamlet').id
        data = {'user_id': user_id, 'failed_tries': 0, 'id': 'test_missed'}
        fake_client.queue.append(('signups', data))

        def fake_publish(queue_name, event, processor):
            # type: (str, Dict[str, Any], Callable[[Any], None]) -> None
            fake_client.queue.append((queue_name, event))

        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.text = ujson.dumps({'title': ''})
        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.SignupWorker()
            worker.setup()
            with patch('zerver.worker.queue_processors.requests.post',
                       return_value=fake_response), \
                    patch('zerver.lib.queue.queue_json_publish',
                          side_effect=fake_publish), \
                    patch('logging.info'), \
                    self.settings(MAILCHIMP_API_KEY='one-two',
                                  PRODUCTION=True,
                                  ZULIP_FRIENDS_LIST_ID='id'):
                worker.start()

        self.assertEqual(data['failed_tries'], 4)

    def test_UserActivityWorker(self):
        # type: () -> None
        fake_client = self.FakeClient()

        user = self.example_user('hamlet')
        UserActivity.objects.filter(
            user_profile = user.id,
            client = get_client('ios')
        ).delete()

        data = dict(
            user_profile_id = user.id,
            client = 'ios',
            time = time.time(),
            query = 'send_message'
        )
        fake_client.queue.append(('user_activity', data))

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.UserActivityWorker()
            worker.setup()
            worker.start()
            activity_records = UserActivity.objects.filter(
                user_profile = user.id,
                client = get_client('ios')
            )
            self.assertTrue(len(activity_records), 1)
            self.assertTrue(activity_records[0].count, 1)

    def test_error_handling(self):
        # type: () -> None
        processed = []

        @queue_processors.assign_queue('unreliable_worker')
        class UnreliableWorker(queue_processors.QueueProcessingWorker):
            def consume(self, data):
                # type: (Mapping[str, Any]) -> None
                if data["type"] == 'unexpected behaviour':
                    raise Exception('Worker task not performing as expected!')
                processed.append(data["type"])

            def _log_problem(self):
                # type: () -> None

                # keep the tests quiet
                pass

        fake_client = self.FakeClient()
        for msg in ['good', 'fine', 'unexpected behaviour', 'back to normal']:
            fake_client.queue.append(('unreliable_worker', {'type': msg}))

        fn = os.path.join(settings.QUEUE_ERROR_DIR, 'unreliable_worker.errors')
        try:
            os.remove(fn)
        except OSError:  # nocoverage # error handling for the directory not existing
            pass

        with simulated_queue_client(lambda: fake_client):
            worker = UnreliableWorker()
            worker.setup()
            worker.start()

        self.assertEqual(processed, ['good', 'fine', 'back to normal'])
        line = open(fn).readline().strip()
        event = ujson.loads(line.split('\t')[1])
        self.assertEqual(event["type"], 'unexpected behaviour')

    def test_worker_noname(self):
        # type: () -> None
        class TestWorker(queue_processors.QueueProcessingWorker):
            def __init__(self):
                # type: () -> None
                super(TestWorker, self).__init__()

            def consume(self, data):
                # type: (Mapping[str, Any]) -> None
                pass  # nocoverage # this is intentionally not called
        with self.assertRaises(queue_processors.WorkerDeclarationException):
            TestWorker()

    def test_worker_noconsume(self):
        # type: () -> None
        @queue_processors.assign_queue('test_worker')
        class TestWorker(queue_processors.QueueProcessingWorker):
            def __init__(self):
                # type: () -> None
                super(TestWorker, self).__init__()

        with self.assertRaises(queue_processors.WorkerDeclarationException):
            worker = TestWorker()
            worker.consume({})
