# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import

import argparse
import logging
import os
import subprocess
import sys

if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import Any, Callable, Dict, List

from zulint.printer import print_err, colors

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

class LinterConfig:
    lint_functions = {}  # type: Dict[str, Callable[[], int]]

    def __init__(self, by_lang):
        # type: (Any) -> None
        self.by_lang = by_lang

    def lint(self, func):
        # type: (Callable[[], int]) -> Callable[[], int]
        self.lint_functions[func.__name__] = func
        return func

    def external_linter(self, name, command, target_langs=[], pass_targets=True):
        # type: (str, List[str], List[str], bool) -> None
        """Registers an external linter program to be run as part of the
        linter.  This program will be passed the subset of files being
        linted that have extensions in target_langs.  If there are no
        such files, exits without doing anything.

        If target_langs is empty, just runs the linter unconditionally.
        """
        color = next(colors)

        def run_linter():
            # type: () -> int
            targets = []  # type: List[str]
            if len(target_langs) != 0:
                targets = [target for lang in target_langs for target in self.by_lang[lang]]
                if len(targets) == 0:
                    # If this linter has a list of languages, and
                    # no files in those languages are to be checked,
                    # then we can safely return success without
                    # invoking the external linter.
                    return 0

            if pass_targets:
                full_command = command + targets
            else:
                full_command = command
            p = subprocess.Popen(full_command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)

            assert p.stdout  # use of subprocess.PIPE indicates non-None
            for line in iter(p.stdout.readline, b''):
                print_err(name, color, line)

            return p.wait()  # Linter exit code

        self.lint_functions[name] = run_linter

    def do_lint(self):
        # type: () -> None
        failed = run_parallel(self.lint_functions)
        sys.exit(1 if failed else 0)
