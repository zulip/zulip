"""
Use libraries from a virtualenv (by modifying sys.path) in production.
Also add Zulip's root directory to sys.path
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
activate_this = os.path.join(
    BASE_DIR,
    "zulip-py3-venv",
    "bin",
    "activate_this.py")
if os.path.exists(activate_this):
    # this file will exist in production
    exec(open(activate_this).read(), {}, dict(__file__=activate_this))
sys.path.append(BASE_DIR)
