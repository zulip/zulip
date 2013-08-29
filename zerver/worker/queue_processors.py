from __future__ import absolute_import

from zerver.lib.queue import SimpleQueueClient

def assign_queue(queue_name):
    def decorate(clazz):
        clazz.queue_name = queue_name
        register_worker(queue_name, clazz)
        return clazz
    return decorate

worker_classes = {}
def register_worker(queue_name, clazz):
    worker_classes[queue_name] = clazz

def get_worker(queue_name):
    return worker_classes[queue_name]()

class QueueProcessingWorker(object):
    def __init__(self):
        self.q = SimpleQueueClient()

    def start(self):
        self.q.register_json_consumer(self.queue_name, self.consume)
        self.q.start_consuming()

    def stop(self):
        self.q.stop_consuming()
