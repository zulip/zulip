from __future__ import print_function
from __future__ import absolute_import

import argparse

from typing import List

from zulint.linters import run_pyflakes


def check_pyflakes(files, options):
    # type: (List[str], argparse.Namespace) -> bool
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
    if options.full:
        suppress_patterns = []
    return run_pyflakes(files, options, suppress_patterns)
