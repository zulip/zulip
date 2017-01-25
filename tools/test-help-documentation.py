#!/usr/bin/env python
from __future__ import print_function
import optparse
import os
import sys
import subprocess

import time

try:
    # We don't actually need typing, but it's a good guard for being
    # outside a Zulip virtualenv.
    from typing import Iterable
    import requests
except ImportError as e:
    print("ImportError: {}".format(e))
    print("You need to run the Zulip tests inside a Zulip dev environment.")
    print("If you are using Vagrant, you can `vagrant ssh` to enter the Vagrant guest.")
    sys.exit(1)

parser = optparse.OptionParser()
parser.add_option('--force', default=False,
                  action="store_true",
                  help='Run tests despite possible problems.')
(options, args) = parser.parse_args()

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TOOLS_DIR))

from tools.lib.test_server import test_server_running

subprocess.check_call(['mkdir', '-p', 'var/help-documentation'])

LOG_FILE = 'var/help-documentation/server.log'
external_host = "localhost:9981"

with test_server_running(options.force, external_host, log_file=LOG_FILE, dots=True, use_db=False):
    ret = subprocess.call(('scrapy', 'crawl_with_status', 'help_documentation_crawler'),
                          cwd='tools/documentation_crawler')

if ret != 0:
    print("\033[0;91m")
    print("Failed")
    print("\033[0m")
else:
    print("\033[0;92m")
    print("Passed!")
    print("\033[0m")


sys.exit(ret)
