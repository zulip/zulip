import argparse
from typing import List

from zulint.linters import run_pyflakes


def check_pyflakes(files: List[str], options: argparse.Namespace) -> bool:
    suppress_patterns = [
        ("scripts/lib/pythonrc.py", "imported but unused"),

        # Our ipython startup pythonrc file intentionally imports *
        ("scripts/lib/pythonrc.py",
         " import *' used; unable to detect undefined names"),

        ("zerver/views/realm.py", "local variable 'message_retention_days' is assigned to but never used"),
        ("settings.py", "settings import *' used; unable to detect undefined names"),
        ("settings.py", "'from .prod_settings_template import *' used; unable to detect undefined names"),
        ("settings.py", "settings.*' imported but unused"),
        ("settings.py", "'.prod_settings_template.*' imported but unused"),

        # Sphinx adds `tags` specially to the environment when running conf.py.
        ("docs/conf.py", "undefined name 'tags'"),
    ]
    if options.full:
        suppress_patterns = []
    return run_pyflakes(files, options, suppress_patterns)
