from timeit import timeit
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.queue import SimpleQueueClient, queue_json_publish
from zerver.worker.queue_processors import BatchNoopWorker, NoopWorker, QueueProcessingWorker


class Command(BaseCommand):
    help = """Times the overhead of enqueuing and dequeuing messages from rabbitmq."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--count", help="Number of messages to enqueue", default=10000, type=int
        )
        parser.add_argument(
            "--reps", help="Iterations of enqueue/dequeue", default=1, type=int
        )
        parser.add_argument(
            "--batch", help="Enables batch dequeuing", action="store_true"
        )
        parser.add_argument(
            "--prefetch",
            help="Limits the prefetch size; rabbitmq defaults to unbounded (0)",
            default=0,
            type=int,
        )
        parser.add_argument(
            "--slow",
            help="Which request numbers should take 60s (1-based)",
            action="append",
            type=int,
            default=[],
        )

    def handle(self, *args: Any, **options: Any) -> None:
        print("Purging queue...")
        queue = SimpleQueueClient()
        queue_name = "noop_batch" if options["batch"] else "noop"
        queue.ensure_queue(queue_name, lambda channel: channel.queue_purge("noop"))

        count = options["count"]
        reps = options["reps"]

        worker: QueueProcessingWorker = NoopWorker(count, options["slow"])
        if options["batch"]:
            worker = BatchNoopWorker(count, options["slow"])
        worker.ENABLE_TIMEOUTS = True
        worker.setup()
        assert worker.q is not None
        assert worker.q.channel is not None
        worker.q.channel.basic_qos(prefetch_count=options["prefetch"])

        total_enqueue_time = 0.0
        total_dequeue_time = 0.0

        def one_rep() -> None:
            nonlocal total_enqueue_time, total_dequeue_time
            total_enqueue_time += timeit(
                lambda: queue_json_publish(queue_name, {}),
                number=count,
            )
            total_dequeue_time += timeit(
                lambda: worker.start(),
                number=1,
            )

        rate = lambda time, iterations: int(iterations/time)

        total_reps_time = timeit(one_rep, number=reps)
        if reps > 1:
            print(f"Total rate per rep: {rate(total_reps_time, reps)} / sec")

        print(f"Enqueue rate: {rate(total_enqueue_time, count * reps)} / sec")
        print(f"Dequeue rate: {rate(total_dequeue_time, count * reps)} / sec")
