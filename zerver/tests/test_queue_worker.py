from __future__ import absolute_import
from __future__ import print_function

import os
import time
import ujson

from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase
from mock import patch
from typing import Any, Callable, Dict, List, Mapping, Tuple

from zerver.lib.test_helpers import simulated_queue_client
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_client, get_user_profile_by_email, UserActivity
from zerver.worker import queue_processors

class WorkerTest(TestCase):
    class FakeClient(object):
        def __init__(self):
            # type: () -> None
            self.consumers = {} # type: Dict[str, Callable]
            self.queue = [] # type: List[Tuple[str, Dict[str, Any]]]

        def register_json_consumer(self, queue_name, callback):
            # type: (str, Callable) -> None
            self.consumers[queue_name] = callback

        def start_consuming(self):
            # type: () -> None
            for queue_name, data in self.queue:
                callback = self.consumers[queue_name]
                callback(data)

    def test_UserActivityWorker(self):
        # type: () -> None
        fake_client = self.FakeClient()

        user = get_user_profile_by_email('hamlet@zulip.com')
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
