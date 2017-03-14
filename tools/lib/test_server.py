from __future__ import print_function

import os
import subprocess
import sys
import time

from contextlib import contextmanager

if False:
    from typing import (Any, Iterator)

try:
    import django
    import requests
except ImportError as e:
    print("ImportError: {}".format(e))
    print("You need to run the Zulip tests inside a Zulip dev environment.")
    print("If you are using Vagrant, you can `vagrant ssh` to enter the Vagrant guest.")
    sys.exit(1)

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, os.path.dirname(TOOLS_DIR))

from zerver.lib.test_fixtures import is_template_database_current

def set_up_django(external_host):
    # type: (str) -> None
    os.environ['EXTERNAL_HOST'] = external_host
    os.environ["TORNADO_SERVER"] = "http://127.0.0.1:9983"
    os.environ['DJANGO_SETTINGS_MODULE'] = 'zproject.test_settings'
    django.setup()
    os.environ['PYTHONUNBUFFERED'] = 'y'

def assert_server_running(server, log_file):
    # type: (subprocess.Popen, str) -> None
    """Get the exit code of the server, or None if it is still running."""
    if server.poll() is not None:
        message = 'Server died unexpectedly!'
        if log_file:
            message += '\nSee %s\n' % (log_file,)
        raise RuntimeError(message)

def server_is_up(server, log_file):
    # type: (subprocess.Popen, str) -> bool
    assert_server_running(server, log_file)
    try:
        # We could get a 501 error if the reverse proxy is up but the Django app isn't.
        return requests.get('http://127.0.0.1:9981/accounts/home').status_code == 200
    except Exception:
        return False

@contextmanager
def test_server_running(force=False, external_host='testserver',
                        log_file=None, dots=False, use_db=True):
    # type: (bool, str, str, bool, bool) -> Iterator[None]
    if log_file:
        if os.path.exists(log_file) and os.path.getsize(log_file) < 100000:
            log = open(log_file, 'a')
            log.write('\n\n')
        else:
            log = open(log_file, 'w')
    else:
        log = sys.stdout # type: ignore # BinaryIO vs. IO[str]

    set_up_django(external_host)

    if use_db:
        generate_fixtures_command = ['tools/setup/generate-fixtures']
        if not is_template_database_current():
            generate_fixtures_command.append('--force')
        subprocess.check_call(generate_fixtures_command)

    # Run this not through the shell, so that we have the actual PID.
    run_dev_server_command = ['tools/run-dev.py', '--test']
    if force:
        run_dev_server_command.append('--force')
    server = subprocess.Popen(run_dev_server_command,
                              stdout=log, stderr=log)

    try:
        # Wait for the server to start up.
        sys.stdout.write('Waiting for test server')
        while not server_is_up(server, log_file):
            if dots:
                sys.stdout.write('.')
                sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\n')

        # DO OUR ACTUAL TESTING HERE!!!
        yield

    finally:
        assert_server_running(server, log_file)
        server.terminate()

if __name__ == '__main__':
    # The code below is for testing this module works
    with test_server_running():
        print('\n\n SERVER IS UP!\n\n')
