"""
Use libraries from a virtualenv (by modifying sys.path) in production.
"""
import os
import sys


def setup_path() -> None:
    if os.path.basename(sys.prefix) != "zulip-py3-venv":
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        venv = os.path.join(BASE_DIR, "zulip-py3-venv")
        activate_this = os.path.join(venv, "bin", "activate_this.py")
        activate_locals = dict(__file__=activate_this)
        with open(activate_this) as f:
            exec(f.read(), activate_locals)  # noqa: S102
        # Check that the python version running this function
        # is same as python version that created the virtualenv.
        python_version = "python{}.{}".format(*sys.version_info[:2])
        if not os.path.exists(os.path.join(venv, "lib", python_version)):
            raise RuntimeError(venv + " was not set up for this Python version")
