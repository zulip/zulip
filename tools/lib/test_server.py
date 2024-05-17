import os
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from typing import Iterator, Optional

# Verify the Zulip venv is available.
from tools.lib import sanity_check

sanity_check.check_venv(__file__)

import django
import requests

MAX_SERVER_WAIT = 180

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, os.path.dirname(TOOLS_DIR))

from scripts.lib.zulip_tools import get_or_create_dev_uuid_var_path
from zerver.lib.test_fixtures import update_test_databases_if_required


def set_up_django(external_host: str) -> None:
    os.environ["FULL_STACK_ZULIP_TEST"] = "1"
    os.environ["TEST_EXTERNAL_HOST"] = external_host
    os.environ["LOCAL_UPLOADS_DIR"] = get_or_create_dev_uuid_var_path("test-backend/test_uploads")
    os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.test_settings"
    django.setup()
    os.environ["PYTHONUNBUFFERED"] = "y"


def assert_server_running(server: "subprocess.Popen[bytes]", log_file: Optional[str]) -> None:
    """Get the exit code of the server, or None if it is still running."""
    if server.poll() is not None:
        message = "Server died unexpectedly!"
        if log_file:
            message += f"\nSee {log_file}\n"
        raise RuntimeError(message)


def server_is_up(server: "subprocess.Popen[bytes]", log_file: Optional[str]) -> bool:
    assert_server_running(server, log_file)
    try:
        # We could get a 501 error if the reverse proxy is up but the Django app isn't.
        # Note that zulipdev.com is mapped via DNS to 127.0.0.1.
        return requests.get("http://zulipdev.com:9981/accounts/home").status_code == 200
    except requests.RequestException:
        return False


@contextmanager
def test_server_running(
    skip_provision_check: bool = False,
    external_host: str = "testserver",
    log_file: Optional[str] = None,
    dots: bool = False,
) -> Iterator[None]:
    with ExitStack() as stack:
        log = sys.stdout
        if log_file:
            if os.path.exists(log_file) and os.path.getsize(log_file) < 100000:
                log = stack.enter_context(open(log_file, "a"))
                log.write("\n\n")
            else:
                log = stack.enter_context(open(log_file, "w"))

        set_up_django(external_host)

        update_test_databases_if_required(rebuild_test_database=True)

        # Run this not through the shell, so that we have the actual PID.
        run_dev_server_command = ["tools/run-dev", "--test", "--streamlined"]
        if skip_provision_check:
            run_dev_server_command.append("--skip-provision-check")
        server = subprocess.Popen(run_dev_server_command, stdout=log, stderr=log)

        try:
            # Wait for the server to start up.
            print(end="\nWaiting for test server (may take a while)")
            if not dots:
                print("\n", flush=True)
            t = time.time()
            while not server_is_up(server, log_file):
                if dots:
                    print(end=".", flush=True)
                time.sleep(0.4)
                if time.time() - t > MAX_SERVER_WAIT:
                    raise Exception("Timeout waiting for server")
            print("\n\n--- SERVER IS UP! ---\n", flush=True)

            # DO OUR ACTUAL TESTING HERE!!!
            yield

        finally:
            assert_server_running(server, log_file)
            server.terminate()
            server.wait()


if __name__ == "__main__":
    # The code below is for testing this module works
    with test_server_running():
        print("\n\n SERVER IS UP!\n\n")
