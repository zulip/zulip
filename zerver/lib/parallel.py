from __future__ import absolute_import
from __future__ import print_function
from typing import Any, Generator, Iterable, Tuple

import os
import pty
import sys
import errno

def run_parallel(job, data, threads=6):
    # type: (Any, Iterable[Any], int) -> Generator[Tuple[int, Any], None, None]
    pids = {} # type: Dict[int, Any]

    def wait_for_one():
        # type: () -> Tuple[int, Any]
        while True:
            try:
                (pid, status) = os.wait()
                return status, pids.pop(pid)
            except KeyError:
                pass

    for item in data:
        pid = os.fork()
        if pid == 0:
            sys.stdin.close()
            try:
                os.close(pty.STDIN_FILENO)
            except OSError as e:
                if e.errno != errno.EBADF:
                    raise
            sys.stdin = open("/dev/null", "r") # type: ignore # py2 and py3 stubs are not compatible
            os._exit(job(item))

        pids[pid] = item
        threads = threads - 1

        if threads == 0:
            (status, item) = wait_for_one()
            threads += 1
            yield (status, item)
            if status != 0:
                # Stop if any error occurred
                break

    while True:
        try:
            (status, item) = wait_for_one()
            yield (status, item)
        except OSError as e:
            if e.errno == errno.ECHILD:
                break
            else:
                raise

if __name__ == "__main__":
    # run some unit tests
    import time
    jobs = [10, 19, 18, 6, 14, 12, 8, 2, 1, 13, 3, 17, 9, 11, 5, 16, 7, 15, 4]
    expected_output = [6, 10, 12, 2, 1, 14, 8, 3, 18, 19, 5, 9, 13, 11, 4, 7, 17, 16, 15]
    def wait_and_print(x):
        # type: (int) -> int
        time.sleep(x * 0.1)
        return 0

    output = []
    for (status, job) in run_parallel(wait_and_print, jobs):
        output.append(job)
    if output == expected_output:
        print("Successfully passed test!")
    else:
        print("Failed test!")
        print(jobs)
        print(expected_output)
        print(output)

