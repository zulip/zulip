"""
Use libraries from a virtualenv (by modifying sys.path) in production.
"""

import os
import sys

from scripts.lib.zulip_tools import is_zulip_production_install


def setup_path() -> None:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Honor UV_PROJECT_ENVIRONMENT / VIRTUAL_ENV so a developer can
    # use a virtualenv at a non-default path.  UV_PROJECT_ENVIRONMENT
    # wins when both are set: it's an explicit target, while
    # VIRTUAL_ENV may be set incidentally by a nearby auto-activated
    # .venv.  Skip on production so a sysadmin's stale VIRTUAL_ENV
    # can't redirect uwsgi or supervisor children.
    if is_zulip_production_install():
        venv_override = None
    else:
        venv_override = os.environ.get("UV_PROJECT_ENVIRONMENT") or os.environ.get("VIRTUAL_ENV")
    venv = os.path.realpath(os.path.join(BASE_DIR, venv_override or ".venv"))
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
