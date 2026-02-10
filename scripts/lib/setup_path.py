"""
Use libraries from a virtualenv (by modifying sys.path) in production.
"""

import os
import sys


def setup_path() -> None:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    venv = os.path.realpath(os.path.join(BASE_DIR, ".venv"))
    if sys.prefix != venv:
        sys.path = list(
            filter(
                # zulip-py3-venv was an historical virtualenv symlink
                lambda p: "/zulip-py3-venv/" not in p and "/.venv/" not in p,
                sys.path,
            )
        )
        activate_this = os.path.join(venv, "bin", "activate_this.py")
        activate_locals = dict(__file__=activate_this)
        with open(activate_this) as f:
            exec(f.read(), activate_locals)  # noqa: S102
        # Check that the python version running this function
        # is same as python version that created the virtualenv.
        python_version = "python{}.{}".format(*sys.version_info[:2])
        if not os.path.exists(os.path.join(venv, "lib", python_version)):
            raise RuntimeError(venv + " was not set up for this Python version")
