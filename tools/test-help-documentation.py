#!/usr/bin/env python
from __future__ import print_function
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

os.environ["EXTERNAL_HOST"] = "localhost:9981"


def assert_server_running(server):
    # type: (subprocess.Popen) -> None
    """Get the exit code of the server, or None if it is still running."""
    if server.poll() is not None:
        raise RuntimeError('Server died unexpectedly! Check %s' % (LOG_FILE,))


def server_is_up(server):
    # type: (subprocess.Popen) -> bool
    assert_server_running(server)
    try:
        # We could get a 501 error if the reverse proxy is up but the Django app isn't.
        return requests.get('http://127.0.0.1:9981/accounts/home').status_code == 200
    except:
        return False


subprocess.check_call(['mkdir', '-p', 'var/help-documentation'])

LOG_FILE = 'var/help-documentation/server.log'
if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) < 100000:
    log = open(LOG_FILE, 'a')
    log.write('\n\n')
else:
    log = open(LOG_FILE, 'w')
server = subprocess.Popen(('tools/run-dev.py', '--test'), stdout=log, stderr=log)
sys.stdout.write('Waiting for test server')
try:
    while not server_is_up(server):
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\n')

    ret = subprocess.call(('scrapy', 'crawl_with_status', 'help_documentation_crawler'),
                          cwd='tools/documentation_crawler')
finally:
    assert_server_running(server)
    server.terminate()

if ret != 0:
    print("\033[0;91m")
    print("Failed")
    print("\033[0m")
else:
    print("\033[0;92m")
    print("Passed!")
    print("\033[0m")


sys.exit(ret)
