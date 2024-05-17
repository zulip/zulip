import csv
from timeit import timeit
from typing import Any, Union

from django.core.management.base import BaseCommand, CommandParser
from typing_extensions import override

from zerver.lib.queue import SimpleQueueClient, queue_json_publish
from zerver.worker.test import BatchNoopWorker, NoopWorker


class Command(BaseCommand):
    help = """Times the overhead of enqueuing and dequeuing messages from RabbitMQ."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--count", help="Number of messages to enqueue", default=10000, type=int
        )
        parser.add_argument("--reps", help="Iterations of enqueue/dequeue", default=1, type=int)
        parser.add_argument("--batch", help="Enables batch dequeuing", action="store_true")
        parser.add_argument("--csv", help="Path to CSV output", default="rabbitmq-timings.csv")
        parser.add_argument(
            "--prefetches",
            help="Limits the prefetch size; RabbitMQ defaults to unbounded (0)",
            default=[0],
            nargs="+",
            type=int,
        )
        parser.add_argument(
            "--slow",
            help="Which request numbers should take 60s (1-based)",
            action="append",
            type=int,
            default=[],
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        print("Purging queue...")
        queue = SimpleQueueClient()
        queue_name = "noop_batch" if options["batch"] else "noop"
        queue.ensure_queue(queue_name, lambda channel: channel.queue_purge("noop"))
        count = options["count"]
        reps = options["reps"]

        with open(options["csv"], "w", newline="") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=["Queue size", "Queue type", "Prefetch", "Rate"]
            )
            writer.writeheader()

            for prefetch in options["prefetches"]:
                print(f"Queue size {count}, prefetch {prefetch}...")
                worker: Union[NoopWorker, BatchNoopWorker] = NoopWorker(count, options["slow"])
                if options["batch"]:
                    worker = BatchNoopWorker(count, options["slow"])
                    if prefetch > 0 and prefetch < worker.batch_size:
                        print(
                            f"    Skipping, as prefetch {prefetch} is less than batch size {worker.batch_size}"
                        )
                        continue
                worker.setup()

                assert worker.q is not None
                assert worker.q.channel is not None
                worker.q.channel.basic_qos(prefetch_count=prefetch)

                total_time = 0.0
                for i in range(1, reps + 1):
                    worker.consumed = 0
                    timeit(
                        lambda: queue_json_publish(queue_name, {}),
                        number=count,
                    )
                    duration = timeit(worker.start, number=1)
                    print(f"    {i}/{reps}: {count}/{duration}s = {count / duration}/s")
                    total_time += duration
                    writer.writerow(
                        {
                            "Queue size": count,
                            "Queue type": queue_name,
                            "Prefetch": prefetch,
                            "Rate": count / duration,
                        }
                    )
                    csvfile.flush()
                print(f"  Overall: {reps * count}/{total_time}s = {(reps * count) / total_time}/s")
