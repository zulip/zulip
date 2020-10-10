from typing import Any, Dict, List
from unittest import mock

import orjson
from django.test import override_settings
from pika.exceptions import AMQPConnectionError, ConnectionClosed

from zerver.lib.queue import TornadoQueueClient, get_queue_client, queue_json_publish
from zerver.lib.test_classes import ZulipTestCase


class TestTornadoQueueClient(ZulipTestCase):
    @mock.patch('zerver.lib.queue.logging.getLogger', autospec=True)
    @mock.patch('zerver.lib.queue.ExceptionFreeTornadoConnection', autospec=True)
    def test_on_open_closed(self, mock_cxn: mock.MagicMock,
                            mock_get_logger: mock.MagicMock) -> None:
        connection = TornadoQueueClient()
        connection.connection.channel.side_effect = ConnectionClosed('500', 'test')
        connection._on_open(mock.MagicMock())


class TestQueueImplementation(ZulipTestCase):
    @override_settings(USING_RABBITMQ=True)
    def test_queue_basics(self) -> None:
        queue_client = get_queue_client()
        queue_client.publish("test_suite", b"test_event\x00\xff")

        with queue_client.drain_queue("test_suite") as result:
            self.assertEqual(result, [b"test_event\x00\xff"])

    @override_settings(USING_RABBITMQ=True)
    def test_queue_basics_json(self) -> None:
        queue_json_publish("test_suite", {"event": "my_event"})

        queue_client = get_queue_client()
        with queue_client.json_drain_queue("test_suite") as result:
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def test_queue_basics_json_error(self) -> None:
        queue_json_publish("test_suite", {"event": "my_event"})

        queue_client = get_queue_client()
        raised = False
        try:
            with queue_client.json_drain_queue("test_suite") as result:
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['event'], 'my_event')
                raise ValueError()
        except ValueError:
            raised = True
        assert raised

        # Still in the queue to be fetched
        with queue_client.json_drain_queue("test_suite") as result:
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def test_register_consumer(self) -> None:
        output = []

        queue_client = get_queue_client()

        def collect(events: List[Dict[str, Any]]) -> None:
            assert len(events) == 1
            output.append(events[0])
            queue_client.stop_consuming()

        queue_json_publish("test_suite", {"event": "my_event"})

        queue_client.start_json_consumer("test_suite", collect)

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def test_register_consumer_nack(self) -> None:
        output = []
        count = 0

        queue_client = get_queue_client()

        def collect(events: List[Dict[str, Any]]) -> None:
            assert len(events) == 1
            queue_client.stop_consuming()
            nonlocal count
            count += 1
            if count == 1:
                raise Exception("Make me nack!")
            output.append(events[0])

        queue_json_publish("test_suite", {"event": "my_event"})

        try:
            queue_client.start_json_consumer("test_suite", collect)
        except Exception:
            queue_client.start_json_consumer("test_suite", collect)

        # Confirm that we processed the event fully once
        self.assertEqual(count, 2)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['event'], 'my_event')

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
                        throw_connection_error_once), self.assertLogs('zulip.queue', level='WARN') as warn_logs:
            queue_json_publish("test_suite", {"event": "my_event"})
        self.assertEqual(warn_logs.output, [
            'WARNING:zulip.queue:Failed to send to rabbitmq, trying to reconnect and send again'
        ])

        assert queue_client.channel
        (_, _, message) = queue_client.channel.basic_get("test_suite")
        assert message
        result = orjson.loads(message)
        self.assertEqual(result['event'], 'my_event')

        (_, _, message) = queue_client.channel.basic_get("test_suite")
        assert not message

    @override_settings(USING_RABBITMQ=True)
    def tearDown(self) -> None:
        queue_client = get_queue_client()
        assert queue_client.channel
        queue_client.channel.queue_purge("test_suite")
        super().tearDown()
