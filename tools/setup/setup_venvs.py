#!/usr/bin/env python3

import os
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

from scripts.lib.setup_venv import setup_virtualenv
from scripts.lib.zulip_tools import run, subprocess_text_output

OLD_VENV_PATH = "/srv/zulip-venv"
VENV_PATH = "/srv/zulip-py3-venv"

DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "dev_lock.txt")

def main(is_travis=False):
    # type: (bool) -> None
    # Get the correct Python interpreter. If we don't do this and use
    # `virtualenv -p python3` to create the venv in Travis, the venv
    # starts referring to the system Python interpreter.
    python_interpreter = subprocess_text_output(['which', 'python3'])
    if is_travis:
        setup_virtualenv(VENV_PATH, DEV_REQS_FILE, patch_activate_script=True,
                         virtualenv_args=['-p', python_interpreter])
    else:
        run(['sudo', 'rm', '-f', OLD_VENV_PATH])
        setup_virtualenv(VENV_PATH, DEV_REQS_FILE, patch_activate_script=True,
                         virtualenv_args=['-p', python_interpreter])

if __name__ == "__main__":
    main()
