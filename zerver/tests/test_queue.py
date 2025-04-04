from typing import Any
from unittest import mock

import orjson
from django.test import override_settings
from pika.exceptions import AMQPConnectionError, ConnectionClosed
from typing_extensions import override

from zerver.lib.queue import (
    SimpleQueueClient,
    TornadoQueueClient,
    get_queue_client,
    queue_json_publish_rollback_unsafe,
)
from zerver.lib.test_classes import ZulipTestCase


class TestTornadoQueueClient(ZulipTestCase):
    @mock.patch("zerver.lib.queue.ExceptionFreeTornadoConnection", autospec=True)
    def test_on_open_closed(self, mock_cxn: mock.MagicMock) -> None:
        with self.assertLogs("zulip.queue", "WARNING") as m:
            mock_cxn().channel.side_effect = ConnectionClosed(500, "test")
            connection = TornadoQueueClient()
            connection._on_open(mock.MagicMock())
            self.assertEqual(
                m.output,
                [
                    "WARNING:zulip.queue:TornadoQueueClient couldn't open channel: connection already closed"
                ],
            )


class TestQueueImplementation(ZulipTestCase):
    @override_settings(USING_RABBITMQ=True)
    def test_register_consumer(self) -> None:
        output = []

        queue_client = get_queue_client()

        def collect(events: list[dict[str, Any]]) -> None:
            assert isinstance(queue_client, SimpleQueueClient)
            assert len(events) == 1
            output.append(events[0])
            queue_client.stop_consuming()

        queue_json_publish_rollback_unsafe("test_suite", {"event": "my_event"})

        queue_client.start_json_consumer("test_suite", collect)

        self.assert_length(output, 1)
        self.assertEqual(output[0]["event"], "my_event")

    @override_settings(USING_RABBITMQ=True)
    def test_register_consumer_nack(self) -> None:
        output = []
        count = 0

        queue_client = get_queue_client()

        def collect(events: list[dict[str, Any]]) -> None:
            assert isinstance(queue_client, SimpleQueueClient)
            assert len(events) == 1
            queue_client.stop_consuming()
            nonlocal count
            count += 1
            if count == 1:
                raise Exception("Make me nack!")
            output.append(events[0])

        queue_json_publish_rollback_unsafe("test_suite", {"event": "my_event"})

        try:
            queue_client.start_json_consumer("test_suite", collect)
        except Exception:
            queue_client.start_json_consumer("test_suite", collect)

        # Confirm that we processed the event fully once
        self.assertEqual(count, 2)
        self.assert_length(output, 1)
        self.assertEqual(output[0]["event"], "my_event")

    @override_settings(USING_RABBITMQ=True)
    def test_queue_error_json(self) -> None:
        queue_client = get_queue_client()
        assert isinstance(queue_client, SimpleQueueClient)
        actual_publish = queue_client.publish

        self.counter = 0

        def throw_connection_error_once(self_obj: Any, *args: Any, **kwargs: Any) -> None:
            self.counter += 1
            if self.counter <= 1:
                raise AMQPConnectionError("test")
            actual_publish(*args, **kwargs)

        with (
            mock.patch("zerver.lib.queue.SimpleQueueClient.publish", throw_connection_error_once),
            self.assertLogs("zulip.queue", level="WARN") as warn_logs,
        ):
            queue_json_publish_rollback_unsafe("test_suite", {"event": "my_event"})
        self.assertEqual(
            warn_logs.output,
            ["WARNING:zulip.queue:Failed to send to rabbitmq, trying to reconnect and send again"],
        )

        assert queue_client.channel
        method, header, message = queue_client.channel.basic_get("test_suite")
        assert method is not None
        assert method.delivery_tag is not None
        assert message is not None
        queue_client.channel.basic_ack(method.delivery_tag)
        result = orjson.loads(message)
        self.assertEqual(result["event"], "my_event")

        method, header, message = queue_client.channel.basic_get("test_suite")
        assert message is None

    @override_settings(USING_RABBITMQ=True)
    @override
    def setUp(self) -> None:
        queue_client = get_queue_client()
        assert queue_client.channel
        queue_client.channel.queue_declare("test_suite", durable=True)
        queue_client.channel.queue_purge("test_suite")
        super().setUp()
