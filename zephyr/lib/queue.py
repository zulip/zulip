from django.conf import settings
import pika
import simplejson

# This simple queuing library doesn't expose much of the power of
# rabbitmq/pika's queuing system; its purpose is to just provide an
# interface for external files to put things into queues and take them
# out from bots without having to import pika code all over our codebase.
class SimpleQueueClient(object):
    connection = None
    channel = None
    queues = set()
    _inited = False

    def __init__(self):
        pass

    def initialize(self):
        # Initialize the connection
        credentials = pika.PlainCredentials('humbug', settings.RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters('localhost',
                                               credentials=credentials)
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self._inited = True

    def create_queue(self, queue_name):
        # Initialize the queues we need
        self.channel.queue_declare(queue=queue_name, durable=True)
        self.queues.add(queue_name)

    def publish(self, queue_name, body):
        if not self._inited:
            self.initialize()
        if queue_name not in self.queues:
            self.create_queue(queue_name)
        self.channel.basic_publish(exchange='',
                                   routing_key=queue_name,
                                   properties=pika.BasicProperties(delivery_mode = 2,),
                                   body=body)

    def json_publish(self, queue_name, body):
        return self.publish(queue_name, simplejson.dumps(body))

    def register_consumer(self, queue_name, callback):
        if not self._inited:
            self.initialize()
        if queue_name not in self.queues:
            self.create_queue(queue_name)

        def wrapped_callback(ch, method, properties, body):
            callback(ch, method, properties, body)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(wrapped_callback, queue=queue_name)

    def register_json_consumer(self, queue_name, callback):
        def wrapped_callback(ch, method, properties, body):
            return callback(ch, method, properties, simplejson.loads(body))
        return self.register_consumer(queue_name, wrapped_callback)

    def start_consuming(self):
        self.channel.start_consuming()
