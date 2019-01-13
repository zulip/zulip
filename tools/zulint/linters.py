from __future__ import print_function
from __future__ import absolute_import

import subprocess
if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import List

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
