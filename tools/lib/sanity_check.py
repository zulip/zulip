#!/usr/bin/env python
from __future__ import print_function

import sys

def check_venv(filename):
    # type: (str) -> None
    try:
        import ujson
    except ImportError:
        print("You need to run %s inside a Zulip dev environment." % (filename,))
        print("If you are using Vagrant, you can `vagrant ssh` to enter the Vagrant guest.")
        sys.exit(1)
