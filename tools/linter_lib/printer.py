from __future__ import print_function
from __future__ import absolute_import

import sys
import os
from itertools import cycle

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib.zulip_tools import ENDC, BOLDRED, GREEN, YELLOW, BLUE, MAGENTA, CYAN

from typing import Union, Text

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
