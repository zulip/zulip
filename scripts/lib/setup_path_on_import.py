"""
Use libraries from a virtualenv (by modifying sys.path) in production.
Also add Zulip's root directory to sys.path
"""

import os
from os.path import dirname, abspath
import sys

BASE_DIR = dirname(dirname(dirname(abspath(__file__))))
activate_this = os.path.join(BASE_DIR, "zulip-venv", "bin", "activate_this.py")
if os.path.exists(activate_this):
    # this file will exist in production
    exec(open(activate_this).read(), {}, dict(__file__=activate_this)) # type: ignore # https://github.com/python/mypy/issues/1577
sys.path.append(BASE_DIR)
