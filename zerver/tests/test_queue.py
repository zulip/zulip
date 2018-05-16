import mock
import os
from typing import Any
import ujson

from django.test import override_settings
from pika.exceptions import ConnectionClosed, AMQPConnectionError

from zerver.lib.queue import TornadoQueueClient, queue_json_publish, \
    get_queue_client, SimpleQueueClient
from zerver.lib.test_classes import ZulipTestCase

class TestTornadoQueueClient(ZulipTestCase):
    @mock.patch('zerver.lib.queue.logging.getLogger', autospec=True)
    @mock.patch('zerver.lib.queue.ExceptionFreeTornadoConnection', autospec=True)
    def test_on_open_closed(self, mock_cxn: mock.MagicMock,
                            mock_get_logger: mock.MagicMock) -> None:
        connection = TornadoQueueClient()
        connection.connection.channel.side_effect = ConnectionClosed
        connection._on_open(mock.MagicMock())


class TestQueueImplementation(ZulipTestCase):
    @override_settings(USING_RABBITMQ=True)
    def test_queue_basics(self) -> None:
        queue_client = get_queue_client()
        queue_client.publish("test_suite", 'test_event')

        result = queue_client.drain_queue("test_suite")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], b'test_event')

    @override_settings(USING_RABBITMQ=True)
    def test_queue_basics_json(self) -> None:
        queue_json_publish("test_suite", {"event": "my_event"})

        queue_client = get_queue_client()
        result = queue_client.drain_queue("test_suite", json=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def test_queue_error_json(self) -> None:
        queue_client = get_queue_client()
        actual_publish = queue_client.publish

        self.counter = 0

        def throw_connection_error_once(self_obj: Any, *args: Any,
                                        **kwargs: Any) -> None:
            self.counter += 1
            if self.counter <= 1:
                raise AMQPConnectionError("test")
            actual_publish(*args, **kwargs)

        with mock.patch("zerver.lib.queue.SimpleQueueClient.publish",
                        throw_connection_error_once):
            queue_json_publish("test_suite", {"event": "my_event"})

        result = queue_client.drain_queue("test_suite", json=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def tearDown(self) -> None:
        queue_client = get_queue_client()
        queue_client.drain_queue("test_suite")
