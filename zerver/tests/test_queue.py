from typing import Any
from unittest import mock

import orjson
from django.test import override_settings
from pika.exceptions import (
    AMQPConnectionError,
    ChannelClosedByBroker,
    ChannelClosedByClient,
    ChannelWrongStateError,
    ConnectionClosed,
    StreamLostError,
)
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
    def test_register_consumer(self, mock_cxn: mock.MagicMock) -> None:
        connection = TornadoQueueClient()
        connection.start_json_consumer("test_suite", lambda events: None)

        channel = mock.MagicMock()
        channel.queue_declare.side_effect = lambda queue, durable, callback: callback(None)
        with self.assertLogs("zulip.queue", "INFO") as m:
            connection._on_channel_open(channel)
        self.assert_length(m.output, 2)
        self.assertTrue(m.output[0].endswith(" to queue test_suite"))
        self.assertEqual(m.output[1], "INFO:zulip.queue:TornadoQueueClient connected")
        self.assertEqual(
            channel.mock_calls,
            [
                mock.call.add_on_close_callback(connection._on_channel_closed),
                mock.call.basic_qos(prefetch_count=100),
                mock.call.queue_declare(queue="test_suite", durable=True, callback=mock.ANY),
                mock.call.basic_consume("test_suite", mock.ANY, consumer_tag=mock.ANY),
            ],
        )

    @mock.patch("zerver.lib.queue.ExceptionFreeTornadoConnection", autospec=True)
    def test_channel_closed_by_broker(self, mock_cxn: mock.MagicMock) -> None:
        connection = TornadoQueueClient()
        channel = mock.MagicMock()
        with self.assertLogs("zulip.queue", "INFO"):
            connection._on_channel_open(channel)

        # Closes from our side, or from losing the connection, are
        # handled by _on_connection_closed.
        connection._on_channel_closed(channel, ChannelClosedByClient(200, "Normal shutdown"))
        connection._on_channel_closed(channel, StreamLostError("Transport indicated EOF"))
        mock_cxn.return_value.close.assert_not_called()

        with self.assertLogs("zulip.queue", "ERROR") as m:
            connection._on_channel_closed(
                channel, ChannelClosedByBroker(406, "PRECONDITION_FAILED")
            )
        self.assertEqual(
            m.output,
            [
                "ERROR:zulip.queue:TornadoQueueClient's channel was closed by RabbitMQ: (406, 'PRECONDITION_FAILED')"
            ],
        )
        mock_cxn.return_value.close.assert_called_once_with()

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

    @mock.patch("zerver.lib.queue.ioloop.IOLoop.current")
    @mock.patch("zerver.lib.queue.ExceptionFreeTornadoConnection", autospec=True)
    def test_publish_while_disconnected(
        self, mock_cxn: mock.MagicMock, mock_ioloop: mock.MagicMock
    ) -> None:
        def open_channel(connection: TornadoQueueClient) -> mock.MagicMock:
            channel = mock.MagicMock()
            connection._on_channel_open(channel)
            return channel

        def declares(channel: mock.MagicMock) -> list[str]:
            return [call.kwargs["queue"] for call in channel.queue_declare.call_args_list]

        def declare_ok(channel: mock.MagicMock, queue_name: str) -> None:
            [declare_callback] = [
                call.kwargs["callback"]
                for call in channel.queue_declare.call_args_list
                if call.kwargs["queue"] == queue_name
            ]
            declare_callback(None)

        def published(channel: mock.MagicMock) -> list[tuple[str, dict[str, str]]]:
            return [
                (call.kwargs["routing_key"], orjson.loads(call.kwargs["body"]))
                for call in channel.basic_publish.call_args_list
            ]

        def reconnect(connection: TornadoQueueClient) -> mock.MagicMock:
            connection._on_connection_closed(mock.MagicMock(), ConnectionClosed(320, "test"))
            connection._reconnect()
            return open_channel(connection)

        with self.assertLogs("zulip.queue", "WARNING") as m:
            connection = TornadoQueueClient()
            connection.json_publish("test_suite", {"event": "first"})
            connection.json_publish("test_suite", {"event": "second"})

            # The connection is lost before the queue is declared, so
            # nothing is published on this channel.
            channel = open_channel(connection)
            self.assertEqual(declares(channel), ["test_suite"])
            channel = reconnect(connection)
            self.assertEqual(declares(channel), ["test_suite"])

            # Publishing to a new queue while connected declares it
            # once, even if more publishes arrive before that completes.
            connection.json_publish("other_queue", {"event": "other"})
            connection.json_publish("other_queue", {"event": "another"})
            self.assertEqual(declares(channel), ["test_suite", "other_queue"])
            channel.basic_publish.assert_not_called()

            declare_ok(channel, "test_suite")
            declare_ok(channel, "other_queue")
            connection.json_publish("test_suite", {"event": "third"})
            self.assertEqual(declares(channel), ["test_suite", "other_queue"])
            self.assertEqual(
                published(channel),
                [
                    ("test_suite", {"event": "first"}),
                    ("test_suite", {"event": "second"}),
                    ("other_queue", {"event": "other"}),
                    ("other_queue", {"event": "another"}),
                    ("test_suite", {"event": "third"}),
                ],
            )

            # Publishes between losing the connection and reconnecting
            # wait for the new channel, rather than using the closed one.
            channel.basic_publish.side_effect = ChannelWrongStateError("Channel is closed.")
            connection._on_connection_closed(mock.MagicMock(), ConnectionClosed(320, "test"))
            connection.json_publish("test_suite", {"event": "fourth"})
            connection._reconnect()
            channel = open_channel(connection)
            declare_ok(channel, "test_suite")
            self.assertEqual(published(channel), [("test_suite", {"event": "fourth"})])

            channel = reconnect(connection)
            channel.queue_declare.assert_not_called()
            channel.basic_publish.assert_not_called()
        self.assertEqual(
            m.output,
            [
                "WARNING:zulip.queue:TornadoQueueClient lost connection to RabbitMQ, reconnecting in 2 secs...",
                "WARNING:zulip.queue:TornadoQueueClient attempting to reconnect to RabbitMQ",
            ]
            * 3,
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
        method, _header, message = queue_client.channel.basic_get("test_suite")
        assert method is not None
        assert method.delivery_tag is not None
        assert message is not None
        queue_client.channel.basic_ack(method.delivery_tag)
        result = orjson.loads(message)
        self.assertEqual(result["event"], "my_event")

        method, _header, message = queue_client.channel.basic_get("test_suite")
        assert message is None

    @override_settings(USING_RABBITMQ=True)
    @override
    def setUp(self) -> None:
        queue_client = get_queue_client()
        assert queue_client.channel
        queue_client.channel.queue_declare("test_suite", durable=True)
        queue_client.channel.queue_purge("test_suite")
        super().setUp()
