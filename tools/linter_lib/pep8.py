from __future__ import print_function
from __future__ import absolute_import

import subprocess
import sys

from .printer import print_err, colors

from typing import List

def check_pep8(files):
    # type: (List[str]) -> bool

    def run_pycodestyle(files, ignored_rules):
        # type: (List[str], List[str]) -> bool
        failed = False
        color = next(colors)
        pep8 = subprocess.Popen(
            ['pycodestyle'] + files + ['--ignore={rules}'.format(rules=','.join(ignored_rules))],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(pep8.stdout.readline, b''):
            print_err('pep8', color, line)
            failed = True
        return failed

    failed = False
    ignored_rules = [
        # Each of these rules are ignored for the explained reason.

        # "multiple spaces before operator"
        # There are several typos here, but also several instances that are
        # being used for alignment in dict keys/values using the `dict`
        # constructor. We could fix the alignment cases by switching to the `{}`
        # constructor, but it makes fixing this rule a little less
        # straightforward.
        'E221',

        # 'missing whitespace around arithmetic operator'
        # This should possibly be cleaned up, though changing some of
        # these may make the code less readable.
        'E226',

        # "unexpected spaces around keyword / parameter equals"
        # Many of these should be fixed, but many are also being used for
        # alignment/making the code easier to read.
        'E251',

        # "block comment should start with '#'"
        # These serve to show which lines should be changed in files customized
        # by the user. We could probably resolve one of E265 or E266 by
        # standardizing on a single style for lines that the user might want to
        # change.
        'E265',

        # "too many leading '#' for block comment"
        # Most of these are there for valid reasons.
        'E266',

        # "expected 2 blank lines after class or function definition"
        # Zulip only uses 1 blank line after class/function
        # definitions; the PEP-8 recommendation results in super sparse code.
        'E302', 'E305',

        # "module level import not at top of file"
        # Most of these are there for valid reasons, though there might be a
        # few that could be eliminated.
        'E402',

        # "line too long"
        # Zulip is a bit less strict about line length, and has its
        # own check for this (see max_length)
        'E501',

        # "do not assign a lambda expression, use a def"
        # Fixing these would probably reduce readability in most cases.
        'E731',
    ]

    # TODO: Clear up this list of violations.
    IGNORE_FILES_PEPE261 = [
        'api/zulip/__init__.py',
        'zerver/tests/test_bugdown.py',
        'zerver/tests/test_events.py',
        'zerver/tests/test_messages.py',
        'zerver/tests/test_narrow.py',
        'zerver/tests/test_outgoing_webhook_system.py',
        'zerver/tests/test_realm.py',
        'zerver/tests/test_signup.py',
        'zerver/tests/test_subs.py',
        'zerver/tests/test_upload.py',
        'zerver/tornado/socket.py',
        'zerver/tornado/websocket_client.py',
        'zerver/worker/queue_processors.py',
        'zilencer/management/commands/populate_db.py',
    ]

    filtered_files = [fn for fn in files if fn not in IGNORE_FILES_PEPE261]
    filtered_files_E261 = [fn for fn in files if fn in IGNORE_FILES_PEPE261]

    if len(files) == 0:
        return False
    if not len(filtered_files) == 0:
        failed = run_pycodestyle(filtered_files, ignored_rules)
    if not len(filtered_files_E261) == 0:
        # Adding an extra ignore rule for these files since they still remain in
        # violation of PEP-E261.
        failed_ignore_e261 = run_pycodestyle(filtered_files_E261, ignored_rules + ['E261'])
        if not failed:
            failed = failed_ignore_e261

    return failed
