# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import

import argparse
import logging
import os
import sys

from typing import Any, Callable, Dict, List

def add_default_linter_arguments(parser):
    # type: (argparse.ArgumentParser) -> None
    parser.add_argument('--modified', '-m',
                        action='store_true',
                        help='Only check modified files')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='Print verbose timing output')
    parser.add_argument('targets',
                        nargs='*',
                        help='Specify directories to check')

def run_parallel(lint_functions):
    # type: (Dict[str, Callable[[], int]]) -> bool
    pids = []
    for name, func in lint_functions.items():
        pid = os.fork()
        if pid == 0:
            logging.info("start " + name)
            result = func()
            logging.info("finish " + name)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(result)
        pids.append(pid)
    failed = False

    for pid in pids:
        (_, status) = os.waitpid(pid, 0)
        if status != 0:
            failed = True
    return failed

def do_lint(lint_functions):
    # type: (Dict[str, Callable[[], int]]) -> None
    failed = run_parallel(lint_functions)
    sys.exit(1 if failed else 0)
