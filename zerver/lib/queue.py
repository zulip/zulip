import logging
import random
import ssl
import threading
import time
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from typing import Any, Callable, Dict, Generic, List, Mapping, Optional, Set, Type, TypeVar, Union

import orjson
import pika
import pika.adapters.tornado_connection
import pika.connection
import pika.exceptions
from django.conf import settings
from pika.adapters.blocking_connection import BlockingChannel
from pika.channel import Channel
from pika.spec import Basic
from tornado import ioloop

from zerver.lib.utils import assert_is_not_none, statsd

MAX_REQUEST_RETRIES = 3
ChannelT = TypeVar("ChannelT", Channel, BlockingChannel)
Consumer = Callable[[ChannelT, Basic.Deliver, pika.BasicProperties, bytes], None]


# This simple queuing library doesn't expose much of the power of
# RabbitMQ/Pika's queuing system; its purpose is to just provide an
# interface for external files to put things into queues and take them
# out from bots without having to import pika code all over our codebase.
class QueueClient(Generic[ChannelT], metaclass=ABCMeta):
    def __init__(
        self,
        # Disable RabbitMQ heartbeats by default because BlockingConnection can't process them
        rabbitmq_heartbeat: Optional[int] = 0,
        prefetch: int = 0,
    ) -> None:
        self.log = logging.getLogger("zulip.queue")
        self.queues: Set[str] = set()
        self.channel: Optional[ChannelT] = None
        self.prefetch = prefetch
        self.consumers: Dict[str, Set[Consumer[ChannelT]]] = defaultdict(set)
        self.rabbitmq_heartbeat = rabbitmq_heartbeat
        self.is_consuming = False
        self._connect()

    @abstractmethod
    def _connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _reconnect(self) -> None:
        raise NotImplementedError

    def _get_parameters(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USERNAME, assert_is_not_none(settings.RABBITMQ_PASSWORD)
        )

        # With BlockingConnection, we are passed
        # self.rabbitmq_heartbeat=0, which asks to explicitly disable
        # the RabbitMQ heartbeat feature.  This is correct since that
        # heartbeat doesn't make sense with BlockingConnection (we do
        # need it for TornadoConnection).
        #
        # Where we've disabled RabbitMQ's heartbeat, the only
        # keepalive on this connection is the TCP keepalive (defaults:
        # `/proc/sys/net/ipv4/tcp_keepalive_*`).  On most Linux
        # systems, the default is to start sending keepalive packets
        # after TCP_KEEPIDLE (7200 seconds) of inactivity; after that
        # point, it send them every TCP_KEEPINTVL (typically 75s).
        # Some Kubernetes / Docker Swarm networks can kill "idle" TCP
        # connections after as little as ~15 minutes of inactivity.
        # To avoid this killing our RabbitMQ connections, we set
        # TCP_KEEPIDLE to something significantly below 15 minutes.
        tcp_options = None
        if self.rabbitmq_heartbeat == 0:
            tcp_options = dict(TCP_KEEPIDLE=60 * 5)

        ssl_options: Union[
            Type[pika.ConnectionParameters._DEFAULT], pika.SSLOptions
        ] = pika.ConnectionParameters._DEFAULT
        if settings.RABBITMQ_USE_TLS:
            ssl_options = pika.SSLOptions(context=ssl.create_default_context())

        return pika.ConnectionParameters(
            settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            heartbeat=self.rabbitmq_heartbeat,
            tcp_options=tcp_options,
            ssl_options=ssl_options,
            credentials=credentials,
        )

    def _generate_ctag(self, queue_name: str) -> str:
        return f"{queue_name}_{str(random.getrandbits(16))}"

    def _reconnect_consumer_callback(self, queue: str, consumer: Consumer[ChannelT]) -> None:
        self.log.info(f"Queue reconnecting saved consumer {consumer} to queue {queue}")
        self.ensure_queue(
            queue,
            lambda channel: channel.basic_consume(
                queue,
                consumer,
                consumer_tag=self._generate_ctag(queue),
            ),
        )

    def _reconnect_consumer_callbacks(self) -> None:
        for queue, consumers in self.consumers.items():
            for consumer in consumers:
                self._reconnect_consumer_callback(queue, consumer)

    def ready(self) -> bool:
        return self.channel is not None

    @abstractmethod
    def ensure_queue(self, queue_name: str, callback: Callable[[ChannelT], object]) -> None:
        raise NotImplementedError

    def publish(self, queue_name: str, body: bytes) -> None:
        def do_publish(channel: ChannelT) -> None:
            channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                properties=pika.BasicProperties(delivery_mode=2),
                body=body,
            )

            statsd.incr(f"rabbitmq.publish.{queue_name}")

        self.ensure_queue(queue_name, do_publish)

    def json_publish(self, queue_name: str, body: Mapping[str, Any]) -> None:
        data = orjson.dumps(body)
        try:
            self.publish(queue_name, data)
            return
        except pika.exceptions.AMQPConnectionError:
            self.log.warning("Failed to send to rabbitmq, trying to reconnect and send again")

        self._reconnect()
        self.publish(queue_name, data)


class SimpleQueueClient(QueueClient[BlockingChannel]):
    connection: Optional[pika.BlockingConnection]

    def _connect(self) -> None:
        start = time.time()
        self.connection = pika.BlockingConnection(self._get_parameters())
        self.channel = self.connection.channel()
        self.log.info(f"SimpleQueueClient connected (connecting took {time.time() - start:.3f}s)")

    def _reconnect(self) -> None:
        self.connection = None
        self.channel = None
        self.queues = set()
        self._connect()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()

    def ensure_queue(self, queue_name: str, callback: Callable[[BlockingChannel], object]) -> None:
        """Ensure that a given queue has been declared, and then call
        the callback with no arguments."""
        if self.connection is None or not self.connection.is_open:
            self._connect()

        assert self.channel is not None
        self.channel.basic_qos(prefetch_count=self.prefetch)

        if queue_name not in self.queues:
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.queues.add(queue_name)

        callback(self.channel)

    def start_json_consumer(
        self,
        queue_name: str,
        callback: Callable[[List[Dict[str, Any]]], None],
        batch_size: int = 1,
        timeout: Optional[int] = None,
    ) -> None:
        if batch_size == 1:
            timeout = None

        def do_consume(channel: BlockingChannel) -> None:
            events: List[Dict[str, Any]] = []
            last_process = time.time()
            max_processed: Optional[int] = None
            self.is_consuming = True

            # This iterator technique will iteratively collect up to
            # batch_size events from the RabbitMQ queue (if present)
            # before calling the callback with the batch.  If not
            # enough events are present, it will sleep for at most
            # timeout seconds before calling the callback with the
            # batch of events it has.
            for method, properties, body in channel.consume(queue_name, inactivity_timeout=timeout):
                if body is not None:
                    assert method is not None
                    events.append(orjson.loads(body))
                    max_processed = method.delivery_tag
                now = time.time()
                if len(events) >= batch_size or (timeout and now >= last_process + timeout):
                    if events:
                        assert max_processed is not None
                        try:
                            callback(events)
                            channel.basic_ack(max_processed, multiple=True)
                        except BaseException:
                            channel.basic_nack(max_processed, multiple=True)
                            raise
                        events = []
                    last_process = now
                if not self.is_consuming:
                    break

        self.ensure_queue(queue_name, do_consume)

    def local_queue_size(self) -> int:
        assert self.channel is not None
        return self.channel.get_waiting_message_count() + len(
            self.channel._pending_events  # type: ignore[attr-defined] # private member missing from stubs
        )

    def stop_consuming(self) -> None:
        assert self.channel is not None
        assert self.is_consuming
        self.is_consuming = False
        self.channel.stop_consuming()


# Patch pika.adapters.tornado_connection.TornadoConnection so that a socket error doesn't
# throw an exception and disconnect the tornado process from the rabbitmq
# queue. Instead, just re-connect as usual
class ExceptionFreeTornadoConnection(pika.adapters.tornado_connection.TornadoConnection):
    def _adapter_disconnect(self) -> None:
        try:
            super()._adapter_disconnect()  # type: ignore[misc]  # private method missing from stubs
        except (
            pika.exceptions.ProbableAuthenticationError,
            pika.exceptions.ProbableAccessDeniedError,
            pika.exceptions.IncompatibleProtocolError,
        ):
            logging.warning(
                "Caught exception in ExceptionFreeTornadoConnection when \
calling _adapter_disconnect, ignoring",
                exc_info=True,
            )


class TornadoQueueClient(QueueClient[Channel]):
    connection: Optional[ExceptionFreeTornadoConnection]

    # Based on:
    # https://pika.readthedocs.io/en/0.9.8/examples/asynchronous_consumer_example.html
    def __init__(self) -> None:
        super().__init__(
            # TornadoConnection can process heartbeats, so enable them.
            rabbitmq_heartbeat=None,
            # Only ask for 100 un-acknowledged messages at once from
            # the server, rather than an unbounded number.
            prefetch=100,
        )
        self._on_open_cbs: List[Callable[[Channel], None]] = []
        self._connection_failure_count = 0

    def _connect(self) -> None:
        self.log.info("Beginning TornadoQueueClient connection")
        self.connection = ExceptionFreeTornadoConnection(
            self._get_parameters(),
            on_open_callback=self._on_open,
            on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_closed,
        )

    def _reconnect(self) -> None:
        self.connection = None
        self.channel = None
        self.queues = set()
        self.log.warning("TornadoQueueClient attempting to reconnect to RabbitMQ")
        self._connect()

    CONNECTION_RETRY_SECS = 2

    # When the RabbitMQ server is restarted, it's normal for it to
    # take a few seconds to come back; we'll retry a few times and all
    # will be well.  So for the first few failures, we report only at
    # "warning" level, avoiding an email to the server admin.
    #
    # A loss of an existing connection starts a retry loop just like a
    # failed connection attempt, so it counts as the first failure.
    #
    # On an unloaded test system, a RabbitMQ restart takes about 6s,
    # potentially causing 4 failures.  We add some headroom above that.
    CONNECTION_FAILURES_BEFORE_NOTIFY = 10

    def _on_connection_open_error(
        self, connection: pika.connection.Connection, reason: Union[str, Exception]
    ) -> None:
        self._connection_failure_count += 1
        retry_secs = self.CONNECTION_RETRY_SECS
        self.log.log(
            logging.CRITICAL
            if self._connection_failure_count > self.CONNECTION_FAILURES_BEFORE_NOTIFY
            else logging.WARNING,
            "TornadoQueueClient couldn't connect to RabbitMQ, retrying in %d secs...",
            retry_secs,
        )
        ioloop.IOLoop.current().call_later(retry_secs, self._reconnect)

    def _on_connection_closed(
        self, connection: pika.connection.Connection, reason: Exception
    ) -> None:
        if self.connection is None:
            return
        self._connection_failure_count = 1
        retry_secs = self.CONNECTION_RETRY_SECS
        self.log.warning(
            "TornadoQueueClient lost connection to RabbitMQ, reconnecting in %d secs...",
            retry_secs,
        )
        ioloop.IOLoop.current().call_later(retry_secs, self._reconnect)

    def _on_open(self, connection: pika.connection.Connection) -> None:
        assert self.connection is not None
        self._connection_failure_count = 0
        try:
            self.connection.channel(on_open_callback=self._on_channel_open)
        except pika.exceptions.ConnectionClosed:
            # The connection didn't stay open long enough for this code to get to it.
            # Let _on_connection_closed deal with trying again.
            self.log.warning("TornadoQueueClient couldn't open channel: connection already closed")

    def _on_channel_open(self, channel: Channel) -> None:
        self.channel = channel
        for callback in self._on_open_cbs:
            callback(channel)
        self._reconnect_consumer_callbacks()
        self.log.info("TornadoQueueClient connected")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def ensure_queue(self, queue_name: str, callback: Callable[[Channel], object]) -> None:
        def set_qos(frame: Any) -> None:
            assert self.channel is not None
            self.queues.add(queue_name)
            self.channel.basic_qos(prefetch_count=self.prefetch, callback=finish)

        def finish(frame: Any) -> None:
            assert self.channel is not None
            callback(self.channel)

        if queue_name not in self.queues:
            # If we're not connected yet, send this message
            # once we have created the channel
            if not self.ready():
                self._on_open_cbs.append(lambda channel: self.ensure_queue(queue_name, callback))
                return

            assert self.channel is not None
            self.channel.queue_declare(queue=queue_name, durable=True, callback=set_qos)
        else:
            assert self.channel is not None
            callback(self.channel)

    def start_json_consumer(
        self,
        queue_name: str,
        callback: Callable[[List[Dict[str, Any]]], None],
        batch_size: int = 1,
        timeout: Optional[int] = None,
    ) -> None:
        def wrapped_consumer(
            ch: Channel,
            method: Basic.Deliver,
            properties: pika.BasicProperties,
            body: bytes,
        ) -> None:
            assert method.delivery_tag is not None
            callback([orjson.loads(body)])
            ch.basic_ack(delivery_tag=method.delivery_tag)

        assert batch_size == 1
        assert timeout is None
        self.consumers[queue_name].add(wrapped_consumer)

        if not self.ready():
            return

        self.ensure_queue(
            queue_name,
            lambda channel: channel.basic_consume(
                queue_name,
                wrapped_consumer,
                consumer_tag=self._generate_ctag(queue_name),
            ),
        )


thread_data = threading.local()


def get_queue_client() -> Union[SimpleQueueClient, TornadoQueueClient]:
    if not hasattr(thread_data, "queue_client"):
        if not settings.USING_RABBITMQ:
            raise RuntimeError("Cannot get a queue client without USING_RABBITMQ")
        thread_data.queue_client = SimpleQueueClient()

    return thread_data.queue_client


def set_queue_client(queue_client: Union[SimpleQueueClient, TornadoQueueClient]) -> None:
    thread_data.queue_client = queue_client


def queue_json_publish(
    queue_name: str,
    event: Dict[str, Any],
    processor: Optional[Callable[[Any], None]] = None,
) -> None:
    if settings.USING_RABBITMQ:
        get_queue_client().json_publish(queue_name, event)
    elif processor:
        processor(event)
    else:
        # Must be imported here: A top section import leads to circular imports
        from zerver.worker.queue_processors import get_worker

        get_worker(queue_name).consume_single_event(event)


def retry_event(
    queue_name: str, event: Dict[str, Any], failure_processor: Callable[[Dict[str, Any]], None]
) -> None:
    if "failed_tries" not in event:
        event["failed_tries"] = 0
    event["failed_tries"] += 1
    if event["failed_tries"] > MAX_REQUEST_RETRIES:
        failure_processor(event)
    else:
        queue_json_publish(queue_name, event)
