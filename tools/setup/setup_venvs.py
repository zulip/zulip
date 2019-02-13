#!/usr/bin/env python3

import os
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

from scripts.lib.setup_venv import setup_virtualenv
from scripts.lib.zulip_tools import overwrite_symlink, subprocess_text_output

VENV_PATH = "/srv/zulip-py3-venv"

DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "dev.txt")
THUMBOR_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "thumbor.txt")

def main() -> None:
    # Get the correct Python interpreter. If we don't do this and use
    # `virtualenv -p python3` to create the venv in Travis, the venv
    # starts referring to the system Python interpreter.
    python_interpreter = subprocess_text_output(['which', 'python3'])
    setup_virtualenv("/srv/zulip-thumbor-venv", THUMBOR_REQS_FILE,
                     patch_activate_script=True, virtualenv_args=['-p', 'python2.7'])
    cached_venv_path = setup_virtualenv(
        VENV_PATH, DEV_REQS_FILE, patch_activate_script=True,
        virtualenv_args=['-p', python_interpreter])
    overwrite_symlink(cached_venv_path, os.path.join(ZULIP_PATH, "zulip-py3-venv"))

if __name__ == "__main__":
    main()
