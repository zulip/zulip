import mock
from typing import Any, Dict

from django.test import override_settings
from pika.exceptions import ConnectionClosed, AMQPConnectionError

from zerver.lib.queue import TornadoQueueClient, queue_json_publish, \
    get_queue_client
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
    def test_register_consumer(self) -> None:
        output = []

        queue_client = get_queue_client()

        def collect(event: Dict[str, Any]) -> None:
            output.append(event)
            queue_client.stop_consuming()

        queue_client.register_json_consumer("test_suite", collect)
        queue_json_publish("test_suite", {"event": "my_event"})

        queue_client.start_consuming()

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def test_register_consumer_nack(self) -> None:
        output = []
        count = 0

        queue_client = get_queue_client()

        def collect(event: Dict[str, Any]) -> None:
            queue_client.stop_consuming()
            nonlocal count
            count += 1
            if count == 1:
                raise Exception("Make me nack!")
            output.append(event)

        queue_client.register_json_consumer("test_suite", collect)
        queue_json_publish("test_suite", {"event": "my_event"})

        try:
            queue_client.start_consuming()
        except Exception:
            queue_client.register_json_consumer("test_suite", collect)
            queue_client.start_consuming()

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
                        throw_connection_error_once):
            queue_json_publish("test_suite", {"event": "my_event"})

        result = queue_client.drain_queue("test_suite", json=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event'], 'my_event')

    @override_settings(USING_RABBITMQ=True)
    def tearDown(self) -> None:
        queue_client = get_queue_client()
        queue_client.drain_queue("test_suite")
