"""
Use libraries from a virtualenv (by modifying sys.path) in production.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

venv = os.path.join(BASE_DIR, "zulip-py3-venv")
if sys.prefix != venv:
    activate_this = os.path.join(venv, "bin", "activate_this.py")
    # this file will exist in production
    if os.path.exists(activate_this):
        activate_locals = dict(__file__=activate_this)
        exec(open(activate_this).read(), {}, activate_locals)
        if not os.path.exists(activate_locals["site_packages"]):
            raise RuntimeError(venv + " was not set up for this Python version")
