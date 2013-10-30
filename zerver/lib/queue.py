from __future__ import absolute_import

from django.conf import settings
import pika
import logging
import ujson
import random
import time
import threading
import atexit
from collections import defaultdict

from zerver.lib.utils import statsd

# This simple queuing library doesn't expose much of the power of
# rabbitmq/pika's queuing system; its purpose is to just provide an
# interface for external files to put things into queues and take them
# out from bots without having to import pika code all over our codebase.
class SimpleQueueClient(object):
    def __init__(self):
        self.log = logging.getLogger('zulip.queue')
        self.queues = set()
        self.channel = None
        self.consumers = defaultdict(set)
        self._connect()

    def _connect(self):
        start = time.time()
        self.connection = pika.BlockingConnection(self._get_parameters())
        self.channel    = self.connection.channel()
        self.log.info('SimpleQueueClient connected (connecting took %.3fs)' % (time.time() - start,))

    def _reconnect(self):
        self.connection = None
        self.channel = None
        self.queues = set()
        self._connect()

    def _get_parameters(self):
        return pika.ConnectionParameters('localhost',
            credentials = pika.PlainCredentials(
                settings.RABBITMQ_USERNAME, settings.RABBITMQ_PASSWORD))

    def _generate_ctag(self, queue_name):
        return "%s_%s" % (queue_name, str(random.getrandbits(16)))

    def _reconnect_consumer_callback(self, queue, consumer):
        self.log.info("Queue reconnecting saved consumer %s to queue %s" % (consumer, queue))
        self.ensure_queue(queue, lambda: self.channel.basic_consume(consumer,
                                                                    queue=queue,
                                                                    consumer_tag=self._generate_ctag(queue)))

    def _reconnect_consumer_callbacks(self):
        for queue, consumers in self.consumers.items():
            for consumer in consumers:
                self._reconnect_consumer_callback(queue, consumer)

    def close(self):
        if self.connection:
            self.connection.close()

    def ready(self):
        return self.channel is not None

    def ensure_queue(self, queue_name, callback):
        '''Ensure that a given queue has been declared, and then call
           the callback with no arguments.'''
        if not self.connection.is_open:
            self._connect()

        if queue_name not in self.queues:
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.queues.add(queue_name)
        callback()

    def publish(self, queue_name, body):
        def do_publish():
            self.channel.basic_publish(
                            exchange='',
                            routing_key=queue_name,
                            properties=pika.BasicProperties(delivery_mode=2),
                            body=body)

            statsd.incr("rabbitmq.publish.%s" % (queue_name,))

        self.ensure_queue(queue_name, do_publish)

    def json_publish(self, queue_name, body):
        try:
            return self.publish(queue_name, ujson.dumps(body))
        except (AttributeError, pika.exceptions.AMQPConnectionError):
            self.log.warning("Failed to send to rabbitmq, trying to reconnect and send again")
            self._reconnect()

            return self.publish(queue_name, ujson.dumps(body))

    def register_consumer(self, queue_name, consumer):
        def wrapped_consumer(ch, method, properties, body):
            try:
                consumer(ch, method, properties, body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception, e:
                ch.basic_nack(delivery_tag=method.delivery_tag)
                raise e

        self.consumers[queue_name].add(wrapped_consumer)
        self.ensure_queue(queue_name,
            lambda: self.channel.basic_consume(wrapped_consumer, queue=queue_name,
                consumer_tag=self._generate_ctag(queue_name)))

    def register_json_consumer(self, queue_name, callback):
        def wrapped_callback(ch, method, properties, body):
            return callback(ujson.loads(body))
        return self.register_consumer(queue_name, wrapped_callback)

    def drain_queue(self, queue_name, json=False):
        "Returns all messages in the desired queue"
        messages =[]
        def opened():
            while True:
                (meta, _, message) = self.channel.basic_get(queue_name)

                if not message:
                    break;

                self.channel.basic_ack(meta.delivery_tag)
                if json:
                    message = ujson.loads(message)
                messages.append(message)

        self.ensure_queue(queue_name, opened)
        return messages

    def start_consuming(self):
        self.channel.start_consuming()

    def stop_consuming(self):
        self.channel.stop_consuming()

# Patch pika.adapters.TornadoConnection so that a socket error doesn't
# throw an exception and disconnect the tornado process from the rabbitmq
# queue. Instead, just re-connect as usual
class ExceptionFreeTornadoConnection(pika.adapters.TornadoConnection):
    def _adapter_disconnect(self):
        try:
            super(ExceptionFreeTornadoConnection, self)._adapter_disconnect()
        except (pika.exceptions.ProbableAuthenticationError,
                pika.exceptions.ProbableAccessDeniedError,
                pika.exceptions.IncompatibleProtocolError) as e:
            logging.warning("Caught exception '%r' in ExceptionFreeTornadoConnection when \
calling _adapter_disconnect, ignoring" % (e,))


class TornadoQueueClient(SimpleQueueClient):
    # Based on:
    # https://pika.readthedocs.org/en/0.9.8/examples/asynchronous_consumer_example.html
    def __init__(self):
        super(TornadoQueueClient, self).__init__()
        self._on_open_cbs = []

    def _connect(self, on_open_cb = None):
        self.log.info("Beginning TornadoQueueClient connection")
        if on_open_cb:
            self._on_open_cbs.append(on_open_cb)
        self.connection = ExceptionFreeTornadoConnection(
            self._get_parameters(),
            on_open_callback = self._on_open,
            stop_ioloop_on_close = False)
        self.connection.add_on_close_callback(self._on_connection_closed)

    def _reconnect(self):
        self.connection = None
        self.channel = None
        self.queues = set()
        self._connect()

    def _on_open(self, connection):
        self.connection.channel(
            on_open_callback = self._on_channel_open)

    def _on_channel_open(self, channel):
        self.channel = channel
        for callback in self._on_open_cbs:
            callback()
        self._reconnect_consumer_callbacks()
        self.log.info('TornadoQueueClient connected')

    def _on_connection_closed(self, connection, reply_code, reply_text):
        self.log.warning("TornadoQueueClient lost connection to RabbitMQ, reconnecting...")
        from tornado import ioloop

        # Try to reconnect in two seconds
        retry_seconds = 2
        def on_timeout():
            try:
                self._reconnect()
            except pika.exceptions.AMQPConnectionError:
                self.log.critical("Failed to reconnect to RabbitMQ, retrying...")
                ioloop.IOLoop.instance().add_timeout(time.time() + retry_seconds, on_timeout)

        ioloop.IOLoop.instance().add_timeout(time.time() + retry_seconds, on_timeout)

    def ensure_queue(self, queue_name, callback):
        def finish(frame):
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

    def register_consumer(self, queue_name, consumer):
        def wrapped_consumer(ch, method, properties, body):
            consumer(ch, method, properties, body)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        if not self.ready():
            self.consumers[queue_name].add(wrapped_consumer)
            return

        self.consumers[queue_name].add(wrapped_consumer)
        self.ensure_queue(queue_name,
            lambda: self.channel.basic_consume(wrapped_consumer, queue=queue_name,
                consumer_tag=self._generate_ctag(queue_name)))

queue_client = None
def get_queue_client():
    global queue_client
    if queue_client is None:
        if settings.RUNNING_INSIDE_TORNADO and settings.USING_RABBITMQ:
            queue_client = TornadoQueueClient()
        elif settings.USING_RABBITMQ:
            queue_client = SimpleQueueClient()

    return queue_client

def setup_tornado_rabbitmq():
    # When tornado is shut down, disconnect cleanly from rabbitmq
    if settings.USING_RABBITMQ:
        atexit.register(lambda: queue_client.close())

# We using a simple lock to prevent multiple RabbitMQ messages being
# sent to the SimpleQueueClient at the same time; this is a workaround
# for an issue with the pika BlockingConnection where using
# BlockingConnection for multiple queues causes the channel to
# randomly close.
queue_lock = threading.RLock()

def queue_json_publish(queue_name, event, processor):
    with queue_lock:
        if settings.USING_RABBITMQ:
            get_queue_client().json_publish(queue_name, event)
        else:
            processor(event)

