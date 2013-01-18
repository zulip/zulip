from django.conf import settings
import pika
import logging
import simplejson
import random

# This simple queuing library doesn't expose much of the power of
# rabbitmq/pika's queuing system; its purpose is to just provide an
# interface for external files to put things into queues and take them
# out from bots without having to import pika code all over our codebase.
class SimpleQueueClient(object):
    def __init__(self):
        self.log = logging.getLogger('humbug.queue')
        self.queues = set()
        self.channel = None
        self._connect()

    def _connect(self):
        self.connection = pika.BlockingConnection(self._get_parameters())
        self.channel    = self.connection.channel()
        self.log.info('SimpleQueueClient connected')

    def _get_parameters(self):
        return pika.ConnectionParameters('localhost',
            credentials = pika.PlainCredentials(
                'humbug', settings.RABBITMQ_PASSWORD))

    def _generate_ctag(self, queue_name):
        return "%s_%s" % (queue_name, str(random.getrandbits(16)))

    def ready(self):
        return self.channel is not None

    def create_queue(self, queue_name):
        # Initialize the queues we need
        self.channel.queue_declare(queue=queue_name, durable=True)
        self.queues.add(queue_name)

    def publish(self, queue_name, body):
        if queue_name not in self.queues:
            self.create_queue(queue_name)
        self.channel.basic_publish(exchange='',
                                   routing_key=queue_name,
                                   properties=pika.BasicProperties(delivery_mode = 2,),
                                   body=body)

    def json_publish(self, queue_name, body):
        return self.publish(queue_name, simplejson.dumps(body))

    def register_consumer(self, queue_name, callback):
        if queue_name not in self.queues:
            self.create_queue(queue_name)

        def wrapped_callback(ch, method, properties, body):
            callback(ch, method, properties, body)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(wrapped_callback, queue=queue_name,
            consumer_tag=self._generate_ctag(queue_name))

    def register_json_consumer(self, queue_name, callback):
        def wrapped_callback(ch, method, properties, body):
            return callback(ch, method, properties, simplejson.loads(body))
        return self.register_consumer(queue_name, wrapped_callback)

    def start_consuming(self):
        self.channel.start_consuming()

    def stop_consuming(self):
        self.channel.stop_consuming()

class TornadoQueueClient(SimpleQueueClient):
    # Based on:
    # https://pika.readthedocs.org/en/0.9.8/examples/asynchronous_consumer_example.html

    def _connect(self):
        self.connection = pika.adapters.TornadoConnection(
            self._get_parameters(),
            on_open_callback = self._on_open)

        # Docs suggest we should also pass stop_ioloop_on_close = False, but
        # my version of TornadoConnection doesn't recognize it.

    def _on_open(self, connection):
        self.connection.channel(
            on_open_callback = self._on_channel_open)

    def _on_channel_open(self, channel):
        self.channel = channel
        self.log.info('TornadoQueueClient connected')
