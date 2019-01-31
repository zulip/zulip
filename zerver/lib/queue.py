
from collections import defaultdict
import logging
import random
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Union

from django.conf import settings
import pika
import pika.adapters.tornado_connection
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic
from tornado import ioloop
import ujson

from zerver.lib.utils import statsd

MAX_REQUEST_RETRIES = 3
Consumer = Callable[[BlockingChannel, Basic.Deliver, pika.BasicProperties, str], None]

# This simple queuing library doesn't expose much of the power of
# rabbitmq/pika's queuing system; its purpose is to just provide an
# interface for external files to put things into queues and take them
# out from bots without having to import pika code all over our codebase.
class SimpleQueueClient:
    def __init__(self,
                 # Disable RabbitMQ heartbeats by default because BlockingConnection can't process them
                 rabbitmq_heartbeat: Optional[int] = 0,
                 ) -> None:
        self.log = logging.getLogger('zulip.queue')
        self.queues = set()  # type: Set[str]
        self.channel = None  # type: Optional[BlockingChannel]
        self.consumers = defaultdict(set)  # type: Dict[str, Set[Consumer]]
        self.rabbitmq_heartbeat = rabbitmq_heartbeat
        self._connect()

    def _connect(self) -> None:
        start = time.time()
        self.connection = pika.BlockingConnection(self._get_parameters())
        self.channel    = self.connection.channel()
        self.log.info('SimpleQueueClient connected (connecting took %.3fs)' % (time.time() - start,))

    def _reconnect(self) -> None:
        self.connection = None
        self.channel = None
        self.queues = set()
        self._connect()

    def _get_parameters(self) -> pika.ConnectionParameters:
        # We explicitly disable the RabbitMQ heartbeat feature, since
        # it doesn't make sense with BlockingConnection
        credentials = pika.PlainCredentials(settings.RABBITMQ_USERNAME,
                                            settings.RABBITMQ_PASSWORD)
        return pika.ConnectionParameters(settings.RABBITMQ_HOST,
                                         heartbeat_interval=self.rabbitmq_heartbeat,
                                         credentials=credentials)

    def _generate_ctag(self, queue_name: str) -> str:
        return "%s_%s" % (queue_name, str(random.getrandbits(16)))

    def _reconnect_consumer_callback(self, queue: str, consumer: Consumer) -> None:
        self.log.info("Queue reconnecting saved consumer %s to queue %s" % (consumer, queue))
        self.ensure_queue(queue, lambda: self.channel.basic_consume(consumer,
                                                                    queue=queue,
                                                                    consumer_tag=self._generate_ctag(queue)))

    def _reconnect_consumer_callbacks(self) -> None:
        for queue, consumers in self.consumers.items():
            for consumer in consumers:
                self._reconnect_consumer_callback(queue, consumer)

    def close(self) -> None:
        if self.connection:
            self.connection.close()

    def ready(self) -> bool:
        return self.channel is not None

    def ensure_queue(self, queue_name: str, callback: Callable[[], None]) -> None:
        '''Ensure that a given queue has been declared, and then call
           the callback with no arguments.'''
        if self.connection is None or not self.connection.is_open:
            self._connect()

        if queue_name not in self.queues:
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.queues.add(queue_name)
        callback()

    def publish(self, queue_name: str, body: str) -> None:
        def do_publish() -> None:
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                properties=pika.BasicProperties(delivery_mode=2),
                body=body)

            statsd.incr("rabbitmq.publish.%s" % (queue_name,))

        self.ensure_queue(queue_name, do_publish)

    def json_publish(self, queue_name: str, body: Union[Mapping[str, Any], str]) -> None:
        # Union because of zerver.middleware.write_log_line uses a str
        try:
            self.publish(queue_name, ujson.dumps(body))
            return
        except pika.exceptions.AMQPConnectionError:
            self.log.warning("Failed to send to rabbitmq, trying to reconnect and send again")

        self._reconnect()
        self.publish(queue_name, ujson.dumps(body))

    def register_consumer(self, queue_name: str, consumer: Consumer) -> None:
        def wrapped_consumer(ch: BlockingChannel,
                             method: Basic.Deliver,
                             properties: pika.BasicProperties,
                             body: str) -> None:
            try:
                consumer(ch, method, properties, body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                ch.basic_nack(delivery_tag=method.delivery_tag)
                raise e

        self.consumers[queue_name].add(wrapped_consumer)
        self.ensure_queue(queue_name,
                          lambda: self.channel.basic_consume(wrapped_consumer, queue=queue_name,
                                                             consumer_tag=self._generate_ctag(queue_name)))

    def register_json_consumer(self, queue_name: str,
                               callback: Callable[[Dict[str, Any]], None]) -> None:
        def wrapped_callback(ch: BlockingChannel,
                             method: Basic.Deliver,
                             properties: pika.BasicProperties,
                             body: str) -> None:
            callback(ujson.loads(body))
        self.register_consumer(queue_name, wrapped_callback)

    def drain_queue(self, queue_name: str, json: bool=False) -> List[Dict[str, Any]]:
        "Returns all messages in the desired queue"
        messages = []

        def opened() -> None:
            while True:
                (meta, _, message) = self.channel.basic_get(queue_name)

                if not message:
                    break

                self.channel.basic_ack(meta.delivery_tag)
                if json:
                    message = ujson.loads(message)
                messages.append(message)

        self.ensure_queue(queue_name, opened)
        return messages

    def start_consuming(self) -> None:
        self.channel.start_consuming()

    def stop_consuming(self) -> None:
        self.channel.stop_consuming()

# Patch pika.adapters.tornado_connection.TornadoConnection so that a socket error doesn't
# throw an exception and disconnect the tornado process from the rabbitmq
# queue. Instead, just re-connect as usual
class ExceptionFreeTornadoConnection(pika.adapters.tornado_connection.TornadoConnection):
    def _adapter_disconnect(self) -> None:
        try:
            super()._adapter_disconnect()
        except (pika.exceptions.ProbableAuthenticationError,
                pika.exceptions.ProbableAccessDeniedError,
                pika.exceptions.IncompatibleProtocolError) as e:
            logging.warning("Caught exception '%r' in ExceptionFreeTornadoConnection when \
calling _adapter_disconnect, ignoring" % (e,))


class TornadoQueueClient(SimpleQueueClient):
    # Based on:
    # https://pika.readthedocs.io/en/0.9.8/examples/asynchronous_consumer_example.html
    def __init__(self) -> None:
        super().__init__(
            # TornadoConnection can process heartbeats, so enable them.
            rabbitmq_heartbeat=None)
        self._on_open_cbs = []  # type: List[Callable[[], None]]
        self._connection_failure_count = 0

    def _connect(self) -> None:
        self.log.info("Beginning TornadoQueueClient connection")
        self.connection = ExceptionFreeTornadoConnection(
            self._get_parameters(),
            on_open_callback = self._on_open,
            on_open_error_callback = self._on_connection_open_error,
            on_close_callback = self._on_connection_closed,
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

    def _on_connection_open_error(self, connection: pika.connection.Connection,
                                  message: Optional[str]=None) -> None:
        self._connection_failure_count += 1
        retry_secs = self.CONNECTION_RETRY_SECS
        message = ("TornadoQueueClient couldn't connect to RabbitMQ, retrying in %d secs..."
                   % (retry_secs,))
        if self._connection_failure_count > self.CONNECTION_FAILURES_BEFORE_NOTIFY:
            self.log.critical(message)
        else:
            self.log.warning(message)
        ioloop.IOLoop.instance().call_later(retry_secs, self._reconnect)

    def _on_connection_closed(self, connection: pika.connection.Connection,
                              reply_code: int, reply_text: str) -> None:
        self._connection_failure_count = 1
        retry_secs = self.CONNECTION_RETRY_SECS
        self.log.warning("TornadoQueueClient lost connection to RabbitMQ, reconnecting in %d secs..."
                         % (retry_secs,))
        ioloop.IOLoop.instance().call_later(retry_secs, self._reconnect)

    def _on_open(self, connection: pika.connection.Connection) -> None:
        self._connection_failure_count = 0
        try:
            self.connection.channel(
                on_open_callback = self._on_channel_open)
        except pika.exceptions.ConnectionClosed:
            # The connection didn't stay open long enough for this code to get to it.
            # Let _on_connection_closed deal with trying again.
            self.log.warning("TornadoQueueClient couldn't open channel: connection already closed")

    def _on_channel_open(self, channel: BlockingChannel) -> None:
        self.channel = channel
        for callback in self._on_open_cbs:
            callback()
        self._reconnect_consumer_callbacks()
        self.log.info('TornadoQueueClient connected')

    def ensure_queue(self, queue_name: str, callback: Callable[[], None]) -> None:
        def finish(frame: Any) -> None:
            self.queues.add(queue_name)
            callback()

        if queue_name not in self.queues:
            # If we're not connected yet, send this message
            # once we have created the channel
            if not self.ready():
                self._on_open_cbs.append(lambda: self.ensure_queue(queue_name, callback))
                return

            self.channel.queue_declare(queue=queue_name, durable=True, callback=finish)
        else:
            callback()

    def register_consumer(self, queue_name: str, consumer: Consumer) -> None:
        def wrapped_consumer(ch: BlockingChannel,
                             method: Basic.Deliver,
                             properties: pika.BasicProperties,
                             body: str) -> None:
            consumer(ch, method, properties, body)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        if not self.ready():
            self.consumers[queue_name].add(wrapped_consumer)
            return

        self.consumers[queue_name].add(wrapped_consumer)
        self.ensure_queue(queue_name,
                          lambda: self.channel.basic_consume(wrapped_consumer, queue=queue_name,
                                                             consumer_tag=self._generate_ctag(queue_name)))

queue_client = None  # type: Optional[SimpleQueueClient]
def get_queue_client() -> SimpleQueueClient:
    global queue_client
    if queue_client is None:
        if settings.RUNNING_INSIDE_TORNADO and settings.USING_RABBITMQ:
            queue_client = TornadoQueueClient()
        elif settings.USING_RABBITMQ:
            queue_client = SimpleQueueClient()

    return queue_client

# We using a simple lock to prevent multiple RabbitMQ messages being
# sent to the SimpleQueueClient at the same time; this is a workaround
# for an issue with the pika BlockingConnection where using
# BlockingConnection for multiple queues causes the channel to
# randomly close.
queue_lock = threading.RLock()

def queue_json_publish(queue_name: str,
                       event: Union[Dict[str, Any], str],
                       processor: Callable[[Any], None]=None) -> None:
    # most events are dicts, but zerver.middleware.write_log_line uses a str
    with queue_lock:
        if settings.USING_RABBITMQ:
            get_queue_client().json_publish(queue_name, event)
        elif processor:
            processor(event)
        else:
            # Must be imported here: A top section import leads to obscure not-defined-ish errors.
            from zerver.worker.queue_processors import get_worker
            get_worker(queue_name).consume_wrapper(event)

def retry_event(queue_name: str,
                event: Dict[str, Any],
                failure_processor: Callable[[Dict[str, Any]], None]) -> None:
    if 'failed_tries' not in event:
        event['failed_tries'] = 0
    event['failed_tries'] += 1
    if event['failed_tries'] > MAX_REQUEST_RETRIES:
        failure_processor(event)
    else:
        queue_json_publish(queue_name, event, lambda x: None)
