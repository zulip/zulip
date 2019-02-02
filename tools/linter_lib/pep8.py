from __future__ import print_function
from __future__ import absolute_import

from zulint.linters import run_pycodestyle

from typing import List

def check_pep8(files):
    # type: (List[str]) -> bool
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

        # New rules in pycodestyle 2.4.0 that we haven't decided whether to comply with yet
        'E252', 'W504',

        # "multiple spaces after ':'"
        # This is the `{}` analogue of E221, and these are similarly being used
        # for alignment.
        'E241',

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

        # "line break before binary operator"
        # This is a bug in the `pep8`/`pycodestyle` tool -- it's completely backward.
        # See https://github.com/PyCQA/pycodestyle/issues/498 .
        'W503',

        # This number will probably be used for the corrected, inverse version of
        # W503 when that's added: https://github.com/PyCQA/pycodestyle/pull/502
        # Once that fix lands and we update to a version of pycodestyle that has it,
        # we'll want the rule; but we might have to briefly ignore it while we fix
        # existing code.
        # 'W504',
    ]

    return run_pycodestyle(files, ignored_rules)
