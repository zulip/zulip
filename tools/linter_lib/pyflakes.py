from __future__ import print_function
from __future__ import absolute_import

import argparse
import subprocess

from zulint.printer import print_err, colors

from typing import List

suppress_patterns = [
    (b"scripts/lib/pythonrc.py", b"imported but unused"),
    (b'', b"'scripts.lib.setup_path_on_import' imported but unused"),

    # Our ipython startup pythonrc file intentionally imports *
    (b"scripts/lib/pythonrc.py",
     b" import *' used; unable to detect undefined names"),

    # Special dev_settings.py import
    (b'', b"from .prod_settings_template import *"),

    (b"settings.py", b"settings import *' used; unable to detect undefined names"),
    (b"settings.py", b"may be undefined, or defined from star imports"),

    # Sphinx adds `tags` specially to the environment when running conf.py.
    (b"docs/conf.py", b"undefined name 'tags'"),
]

def suppress_line(line: str) -> bool:
    for file_pattern, line_pattern in suppress_patterns:
        if file_pattern in line and line_pattern in line:
            return True
    return False

def check_pyflakes(files, options):
    # type: (List[str], argparse.Namespace) -> bool
    if len(files) == 0:
        return False
    failed = False
    color = next(colors)
    pyflakes = subprocess.Popen(['pyflakes'] + files,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    assert pyflakes.stdout is not None  # Implied by use of subprocess.PIPE
    for ln in pyflakes.stdout.readlines() + pyflakes.stderr.readlines():
        if options.full or not suppress_line(ln):
            print_err('pyflakes', color, ln)
            failed = True
    return failed
