#!/usr/bin/env python
from __future__ import print_function

import sys

import getpass

def check_venv(filename):
    # type: (str) -> None
    try:
        import ujson
    except ImportError:
        print("You need to run %s inside a Zulip dev environment." % (filename,))
        username = getpass.getuser()
        if username != 'vagrant':
            print("If you are using Vagrant, you can `vagrant ssh` to enter the Vagrant guest.")
        else:
            print("You can `source /srv/zulip-venv/bin/activate` to enter dev environment.")
        sys.exit(1)
