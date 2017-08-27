#!/usr/bin/env python3
from __future__ import print_function
from __future__ import absolute_import
import optparse
import os
import sys
import subprocess

import time

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# check for the venv
from lib import sanity_check
sanity_check.check_venv(__file__)

import requests

parser = optparse.OptionParser()
parser.add_option('--force', default=False,
                  action="store_true",
                  help='Run tests despite possible problems.')
(options, args) = parser.parse_args()

os.chdir(ZULIP_PATH)
sys.path.insert(0, ZULIP_PATH)
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
