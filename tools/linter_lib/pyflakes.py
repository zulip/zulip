from __future__ import print_function
from __future__ import absolute_import

import subprocess
import sys

from typing import Any, Dict, List

def check_pyflakes(options, by_lang):
    # type: (Any, Dict[str, List[str]]) -> bool
    if len(by_lang['py']) == 0:
        return False
    failed = False
    pyflakes = subprocess.Popen(['pyflakes'] + by_lang['py'],
                                stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE,
                                universal_newlines = True)

    # pyflakes writes some output (like syntax errors) to stderr. :/
    for pipe in (pyflakes.stdout, pyflakes.stderr):
        assert(pipe is not None)  # convince mypy that pipe cannot be None
        for ln in pipe:
            if options.full or not (
                    ('imported but unused' in ln or
                     'redefinition of unused' in ln or
                     # Our ipython startup pythonrc file intentionally imports *
                     ("scripts/lib/pythonrc.py" in ln and
                      " import *' used; unable to detect undefined names" in ln) or
                     # Special dev_settings.py import
                     "from .prod_settings_template import *" in ln or
                     ("settings.py" in ln and
                      ("settings import *' used; unable to detect undefined names" in ln or
                       "may be undefined, or defined from star imports" in ln)) or
                     ("zerver/tornado/ioloop_logging.py" in ln and
                      "redefinition of function 'instrument_tornado_ioloop'" in ln) or
                     ("zephyr_mirror_backend.py:" in ln and
                      "redefinition of unused 'simplejson' from line" in ln))):
                sys.stdout.write(ln)
                failed = True
    return failed
