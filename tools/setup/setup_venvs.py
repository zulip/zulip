#!/usr/bin/env python3

import os
import sys
from os.path import dirname, abspath

ZULIP_PATH = dirname(dirname(dirname(abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

from scripts.lib.setup_venv import setup_virtualenv
from scripts.lib.zulip_tools import run

OLD_VENV_PATH = "/srv/zulip-venv"
VENV_PATH = "/srv/zulip-py3-venv"

DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "dev_lock.txt")

def main(is_travis=False):
    # type: (bool) -> None
    if is_travis:
        setup_virtualenv(VENV_PATH, DEV_REQS_FILE, patch_activate_script=True,
                         virtualenv_args=['-p', 'python3'])
    else:
        run(['sudo', 'rm', '-f', OLD_VENV_PATH])
        setup_virtualenv(VENV_PATH, DEV_REQS_FILE, patch_activate_script=True,
                         virtualenv_args=['-p', 'python3'])

if __name__ == "__main__":
    main()
