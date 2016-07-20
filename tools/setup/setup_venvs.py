#!/usr/bin/env python

import os
import sys
from os.path import dirname, abspath

ZULIP_PATH = dirname(dirname(dirname(abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

from scripts.lib.setup_venv import setup_virtualenv

def main():
    # type: () -> None
    PY2_DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "py2_dev.txt")
    setup_virtualenv("/srv/zulip-venv", PY2_DEV_REQS_FILE, patch_activate_script=True)

    PY3_DEV_REQS_FILE = os.path.join(ZULIP_PATH, "requirements", "py3_dev.txt")
    setup_virtualenv("/srv/zulip-py3-venv", PY3_DEV_REQS_FILE, patch_activate_script=True,
                     virtualenv_args=['-p', 'python3'])

if __name__ == "__main__":
    main()
