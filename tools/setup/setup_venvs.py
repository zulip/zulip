#!/usr/bin/env python

import os
import sys
from os.path import dirname, abspath

ZULIP_PATH = dirname(dirname(dirname(abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

from scripts.lib.setup_venv import setup_virtualenv
from scripts.lib.zulip_tools import run

PY2_VENV_PATH = "/srv/zulip-venv"
PY3_VENV_PATH = "/srv/zulip-py3-venv"

PY2_DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "py2_dev.txt")
PY3_DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "py3_dev.txt")

PY2 = sys.version_info[0] == 2

def main(is_travis=False):
    # type: (bool) -> None
    if is_travis:
        if PY2:
            MYPY_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "mypy.txt")
            setup_virtualenv(PY3_VENV_PATH, MYPY_REQS_FILE, patch_activate_script=True,
                             virtualenv_args=['-p', 'python3'])
            setup_virtualenv(PY2_VENV_PATH, PY2_DEV_REQS_FILE, patch_activate_script=True)
        else:
            setup_virtualenv(PY3_VENV_PATH, PY3_DEV_REQS_FILE, patch_activate_script=True,
                             virtualenv_args=['-p', 'python3'])
    else:
        run(['sudo', 'rm', '-f', PY2_VENV_PATH])
        setup_virtualenv(PY3_VENV_PATH, PY3_DEV_REQS_FILE, patch_activate_script=True,
                         virtualenv_args=['-p', 'python3'])

if __name__ == "__main__":
    main()
