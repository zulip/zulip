import glob
import logging
import os
import shutil
import tempfile
from collections import Counter
from multiprocessing import Manager, current_process
from threading import Barrier

from django.db import connection

from zerver.lib.parallel import _disconnect, run_parallel, run_parallel_queue
from zerver.lib.partial import partial
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Realm


class RunNotParallelTest(ZulipTestCase):
    def test_disconnect(self) -> None:
        self.assertTrue(connection.is_usable())
        self.assertEqual(Realm.objects.count(), 4)
        _disconnect()
        self.assertFalse(connection.is_usable())

    def test_not_parallel(self) -> None:
        # Nothing here is parallel, or forks at all
        events = []

        run_parallel(
            lambda item: events.append(f"Item: {item}"),
            range(100, 110),
            processes=1,
            initializer=lambda a, b: events.append(f"Init: {a}, {b}"),
            initargs=("alpha", "bravo"),
            report_every=3,
            report=lambda n: events.append(f"Completed {n}"),
        )

        self.assertEqual(
            events,
            [
                "Init: alpha, bravo",
                "Item: 100",
                "Item: 101",
                "Item: 102",
                "Completed 3",
                "Item: 103",
                "Item: 104",
                "Item: 105",
                "Completed 6",
                "Item: 106",
                "Item: 107",
                "Item: 108",
                "Completed 9",
                "Item: 109",
            ],
        )

    def test_not_parallel_throw(self) -> None:
        events = []

        def do_work(item: int) -> None:
            if item == 103:
                raise Exception("I don't like threes")
            events.append(f"Item: {item}")

        with self.assertRaisesRegex(Exception, "I don't like threes"):
            run_parallel(
                do_work,
                range(100, 110),
                processes=1,
                report_every=5,
                report=lambda n: events.append(f"Completed {n}"),
                catch=False,
            )

        self.assertEqual(
            events,
            [
                "Item: 100",
                "Item: 101",
                "Item: 102",
            ],
        )

    def test_not_parallel_catch(self) -> None:
        events = []

        def do_work(item: int) -> None:
            if item == 103:
                raise Exception("I don't like threes")
            events.append(f"Item: {item}")

        with self.assertLogs(level="ERROR") as error_logs:
            run_parallel(
                do_work,
                range(100, 105),
                processes=1,
                report_every=5,
                report=lambda n: events.append(f"Completed {n}"),
                catch=True,
            )

        self.assert_length(error_logs.output, 1)
        self.assertTrue(
            error_logs.output[0].startswith("ERROR:root:Error processing item: 103\nTraceback")
        )
        self.assertIn("I don't like threes", error_logs.output[0])

        self.assertEqual(
            events,
            [
                "Item: 100",
                "Item: 101",
                "Item: 102",
                "Item: 104",
                # We "completed" the one which raised an exception,
                # despite it not having output
                "Completed 5",
            ],
        )

    def test_not_parallel_queue(self) -> None:
        events = []

        with run_parallel_queue(
            lambda item: events.append(f"Item: {item}"),
            processes=1,
            report_every=3,
            report=lambda n: events.append(f"Completed {n}"),
            initializer=lambda a, b: events.append(f"Init: {a}, {b}"),
            initargs=("alpha", "bravo"),
        ) as do_work:
            self.assertEqual(events, ["Init: alpha, bravo"])
            do_work(100)
            self.assertEqual(
                events,
                [
                    "Init: alpha, bravo",
                    "Item: 100",
                ],
            )
            do_work(101)
            do_work(102)
        self.assertEqual(
            events,
            [
                "Init: alpha, bravo",
                "Item: 100",
                "Item: 101",
                "Item: 102",
                "Completed 3",
            ],
        )


def write_number(
    output_dir: str, barrier: Barrier, fail: set[int], item: int
) -> None:  # nocoverage
    if item in fail:
        raise Exception("Whoops")

    output_file = f"{output_dir}/{os.getpid()}.output"
    first_time = not os.path.exists(output_file)
    with open(output_file, "a") as fh:
        fh.write(f"{item}\n")
    # If this is our first time through, we wait until every PID has
    # gotten a chance to consume one value before carrying on to
    # consume our second.
    if first_time:
        barrier.wait(60)


def db_query(output_dir: str, barrier: Barrier, item: int) -> None:  # nocoverage
    connection.connect()
    output_file = f"{output_dir}/{os.getpid()}.output"
    first_time = not os.path.exists(output_file)
    with open(output_file, "a") as fh:
        fh.write(f"{Realm.objects.count()}\n")
    if first_time:
        barrier.wait(60)


class RunParallelTest(ZulipTestCase):
    def skip_in_parallel_harness(self) -> None:
        if current_process().daemon:
            self.skipTest("Testing of parallel pool is skipped under the parallel test harness")

    def test_parallel(self) -> None:  # nocoverage
        self.skip_in_parallel_harness()

        output_dir = tempfile.mkdtemp()
        report_lines = []
        try:
            barrier = Manager().Barrier(4)
            run_parallel(
                partial(write_number, output_dir, barrier, set()),
                range(100, 110),
                processes=4,
                report_every=3,
                report=lambda n: report_lines.append(f"Completed {n}"),
            )

            files = glob.glob(f"{output_dir}/*.output")
            self.assert_length(files, 4)
            all_lines: Counter[str] = Counter()
            for output_path in files:
                with open(output_path) as output_file:
                    file_lines = output_file.readlines()
                    self.assertGreater(len(file_lines), 0)
                    self.assertLessEqual(len(file_lines), 10 - (4 - 1))
                    self.assertEqual(sorted(file_lines), file_lines)
                    all_lines.update(file_lines)

            self.assertEqual(all_lines.total(), 10)
            self.assertEqual(sorted(all_lines.keys()), [f"{n}\n" for n in range(100, 110)])

            self.assertEqual(report_lines, ["Completed 3", "Completed 6", "Completed 9"])
        finally:
            shutil.rmtree(output_dir)

    def test_parallel_throw(self) -> None:  # nocoverage
        self.skip_in_parallel_harness()
        output_dir = tempfile.mkdtemp()
        report_lines = []
        try:
            barrier = Manager().Barrier(2)
            with self.assertRaisesMessage(Exception, "Whoops"):
                run_parallel(
                    partial(write_number, output_dir, barrier, {103}),
                    range(100, 105),
                    processes=2,
                    report_every=5,
                    report=lambda n: report_lines.append(f"Completed {n}"),
                )
            output_files = glob.glob(f"{output_dir}/*.output")
            self.assert_length(output_files, 2)
            all_lines: set[int] = set()
            for output_path in output_files:
                with open(output_path) as output_file:
                    all_lines.update(int(line) for line in output_file)
            self.assertIn(100, all_lines)
            self.assertIn(101, all_lines)
            self.assertNotIn(103, all_lines)
            self.assertEqual(report_lines, [])
        finally:
            shutil.rmtree(output_dir)

    def test_parallel_catch(self) -> None:  # nocoverage
        self.skip_in_parallel_harness()
        output_dir = tempfile.mkdtemp()
        report_lines = []

        def set_file_logger(output_dir: str) -> None:
            # In each worker process, we set up the logger to write to
            # a (pid).error file.
            logging.basicConfig(
                filename=f"{output_dir}/{os.getpid()}.error",
                level=logging.INFO,
                filemode="w",
                force=True,
            )

        try:
            barrier = Manager().Barrier(2)
            run_parallel(
                partial(write_number, output_dir, barrier, {103}),
                range(100, 105),
                processes=2,
                report_every=5,
                report=lambda n: report_lines.append(f"Completed {n}"),
                catch=True,
                initializer=set_file_logger,
                initargs=(output_dir,),
            )
            output_files = glob.glob(f"{output_dir}/*.output")
            self.assert_length(output_files, 2)
            all_lines: set[int] = set()
            for output_path in output_files:
                with open(output_path) as output_file:
                    all_lines.update(int(line) for line in output_file)
            self.assertEqual(sorted(all_lines), [100, 101, 102, 104])
            self.assertEqual(report_lines, ["Completed 5"])

            error_files = glob.glob(f"{output_dir}/*.error")
            error_lines = []
            self.assert_length(error_files, 2)
            for error_path in error_files:
                with open(error_path) as error_file:
                    error_lines.extend(error_file.readlines())
            self.assertEqual(error_lines[0], "ERROR:root:Error processing item: 103\n")
        finally:
            shutil.rmtree(output_dir)

    def test_parallel_reconnect(self) -> None:  # nocoverage
        self.skip_in_parallel_harness()
        output_dir = tempfile.mkdtemp()
        barrier = Manager().Barrier(2)
        run_parallel(
            partial(db_query, output_dir, barrier),
            range(100, 105),
            processes=2,
        )
        output_files = glob.glob(f"{output_dir}/*.output")
        self.assert_length(output_files, 2)
        all_lines: set[int] = set()
        for output_path in output_files:
            with open(output_path) as output_file:
                all_lines.update(int(line) for line in output_file)
        self.assertEqual(all_lines, {4})
