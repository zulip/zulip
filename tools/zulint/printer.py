from __future__ import print_function
from __future__ import absolute_import

import sys
from itertools import cycle
if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import Union, Text

# Terminal Color codes for use in differentiatng linters
BOLDRED = '\x1B[1;31m'
GREEN = '\x1b[32m'
YELLOW = '\x1b[33m'
BLUE = '\x1b[34m'
MAGENTA = '\x1b[35m'
CYAN = '\x1b[36m'
ENDC = '\033[0m'

colors = cycle([GREEN, YELLOW, BLUE, MAGENTA, CYAN])

def print_err(name, color, line):
    # type: (str, str, Union[Text, bytes]) -> None

    # Decode with UTF-8 if in Python 3 and `line` is of bytes type.
    # (Python 2 does this automatically)
    if sys.version_info[0] == 3 and isinstance(line, bytes):
        line = line.decode('utf-8')

    print('{}{}{}|{end} {}{}{end}'.format(
        color,
        name,
        ' ' * max(0, 10 - len(name)),
        BOLDRED,
        line.rstrip(),
        end=ENDC)
    )

    # Python 2's print function does not have a `flush` option.
    sys.stdout.flush()
