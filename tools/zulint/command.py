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
    from typing import Callable, Dict, List, Optional

from zulint.printer import print_err, colors, BOLDRED, BLUE, GREEN, ENDC
from zulint import lister

def add_default_linter_arguments(parser):
    # type: (argparse.ArgumentParser) -> None
    parser.add_argument('--modified', '-m',
                        action='store_true',
                        help='Only check modified files')
    parser.add_argument('--verbose-timing', '-vt',
                        action='store_true',
                        help='Print verbose timing output')
    parser.add_argument('targets',
                        nargs='*',
                        help='Specify directories to check')
    parser.add_argument('--skip',
                        default=[],
                        type=split_arg_into_list,
                        help='Specify linters to skip, eg: --skip=mypy,gitlint')
    parser.add_argument('--only',
                        default=[],
                        type=split_arg_into_list,
                        help='Specify linters to run, eg: --only=mypy,gitlint')
    parser.add_argument('--list', '-l',
                        action='store_true',
                        help='List all the registered linters')
    parser.add_argument('--list-groups', '-lg',
                        action='store_true',
                        help='List all the registered linter groups')
    parser.add_argument('--groups', '-g',
                        default=[],
                        type=split_arg_into_list,
                        help='Only run linter for languages in the group(s), e.g.: '
                        '--groups=backend,frontend')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='Print verbose output where available')
    parser.add_argument('--fix',
                        action='store_true',
                        help='Automatically fix problems where supported')

def split_arg_into_list(arg):
    # type: (str) -> List[str]
    return [linter for linter in arg.split(',')]

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
    lint_descriptions = {}  # type: Dict[str, str]

    def __init__(self, args):
        # type: (argparse.Namespace) -> None
        self.args = args
        self.by_lang = {}  # type: Dict[str, List[str]]
        self.groups = {}  # type: Dict[str, List[str]]

    def list_files(self, file_types=[], groups={}, use_shebang=True, group_by_ftype=True, exclude=[]):
        # type: (List[str], Dict[str, List[str]], bool, bool, List[str]) -> Dict[str, List[str]]
        assert file_types or groups, "Atleast one of `file_types` or `groups` must be specified."

        self.groups = groups
        if self.args.groups:
            file_types = [ft for group in self.args.groups for ft in groups[group]]
        else:
            file_types.extend({ft for group in groups.values() for ft in group})

        self.by_lang = lister.list_files(self.args.targets, modified_only=self.args.modified,
                                         ftypes=file_types, use_shebang=use_shebang,
                                         group_by_ftype=group_by_ftype, exclude=exclude)
        return self.by_lang

    def lint(self, func):
        # type: (Callable[[], int]) -> Callable[[], int]
        self.lint_functions[func.__name__] = func
        self.lint_descriptions[func.__name__] = func.__doc__ if func.__doc__ else "External Linter"
        return func

    def external_linter(self, name, command, target_langs=[], pass_targets=True, fix_arg=None,
                        description="External Linter"):
        # type: (str, List[str], List[str], bool, Optional[str], str) -> None
        """Registers an external linter program to be run as part of the
        linter.  This program will be passed the subset of files being
        linted that have extensions in target_langs.  If there are no
        such files, exits without doing anything.

        If target_langs is empty, just runs the linter unconditionally.
        """
        self.lint_descriptions[name] = description
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

            if self.args.fix and fix_arg:
                command.append(fix_arg)

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

    def set_logger(self):
        # type: () -> None
        logging.basicConfig(format="%(asctime)s %(message)s")
        logger = logging.getLogger()
        if self.args.verbose_timing:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.WARNING)

    def do_lint(self):
        # type: () -> None
        assert not self.args.only or not self.args.skip, "Only one of --only or --skip can be used at once."
        if self.args.only:
            self.lint_functions = {linter: self.lint_functions[linter] for linter in self.args.only}
        for linter in self.args.skip:
            del self.lint_functions[linter]
        if self.args.list:
            print("{}{:<15} {} {}".format(BOLDRED, 'Linter', 'Description', ENDC))
            for linter, desc in self.lint_descriptions.items():
                print("{}{:<15} {}{}{}".format(BLUE, linter, GREEN, desc, ENDC))
            sys.exit()
        if self.args.list_groups:
            print("{}{:<15} {} {}".format(BOLDRED, 'Linter Group', 'File types', ENDC))
            for group, file_types in self.groups.items():
                print("{}{:<15} {}{}{}".format(BLUE, group, GREEN, ", ".join(file_types), ENDC))
            sys.exit()
        self.set_logger()

        failed = run_parallel(self.lint_functions)
        sys.exit(1 if failed else 0)
