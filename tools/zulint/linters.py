from __future__ import print_function
from __future__ import absolute_import

import argparse
import subprocess
if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import List, Tuple

from zulint.printer import print_err, colors


def run_pycodestyle(files, ignored_rules):
    # type: (List[str], List[str]) -> bool
    if len(files) == 0:
        return False

    failed = False
    color = next(colors)
    pep8 = subprocess.Popen(
        ['pycodestyle'] + files + ['--ignore={rules}'.format(rules=','.join(ignored_rules))],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert pep8.stdout is not None  # Implied by use of subprocess.PIPE
    for line in iter(pep8.stdout.readline, b''):
        print_err('pep8', color, line)
        failed = True
    return failed


def run_pyflakes(files, options, suppress_patterns=[]):
    # type: (List[str], argparse.Namespace, List[Tuple[str, str]]) -> bool
    if len(files) == 0:
        return False
    failed = False
    color = next(colors)
    pyflakes = subprocess.Popen(['pyflakes'] + files,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    assert pyflakes.stdout is not None  # Implied by use of subprocess.PIPE

    def suppress_line(line: str) -> bool:
        for file_pattern, line_pattern in suppress_patterns:
            if file_pattern in line and line_pattern in line:
                return True
        return False

    for ln in pyflakes.stdout.readlines() + pyflakes.stderr.readlines():
        if options.full or not suppress_line(ln):
            print_err('pyflakes', color, ln)
            failed = True
    return failed
