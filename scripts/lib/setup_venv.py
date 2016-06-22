from __future__ import print_function

import os
import sys
from os.path import dirname, abspath
import subprocess
from zulip_tools import run

ZULIP_PATH = dirname(dirname(dirname(abspath(__file__))))
VENV_CACHE_PATH = "/srv/zulip-venv-cache"

if '--travis' in sys.argv:
    # In Travis CI, we don't have root access
    VENV_CACHE_PATH = os.path.join(os.environ['HOME'], "zulip-venv-cache")

if False:
    # Don't add a runtime dependency on typing
    from typing import List

VENV_DEPENDENCIES = [
    "libffi-dev",
    "libfreetype6-dev",
    "libldap2-dev",
    "libmemcached-dev",
    "postgresql-server-dev-all",
    "python3-dev",          # Needed to install typed-ast dependency of mypy
    "python-dev",
    "python-virtualenv",
]

def setup_virtualenv(target_venv_path, requirements_file, virtualenv_args=None):
    # type: (str, str, List[str]) -> None

    # Check if a cached version already exists
    path = os.path.join(ZULIP_PATH, 'scripts', 'lib', 'hash_reqs.py')
    output = subprocess.check_output([path, requirements_file])
    sha1sum = output.split()[0]
    cached_venv_path = os.path.join(VENV_CACHE_PATH, sha1sum, os.path.basename(target_venv_path))
    success_stamp = os.path.join(cached_venv_path, "success-stamp")
    if not os.path.exists(success_stamp):
        do_setup_virtualenv(cached_venv_path, requirements_file, virtualenv_args or [])
        run(["touch", success_stamp])

    print("Using cached Python venv from %s" % (cached_venv_path,))
    run(["sudo", "ln", "-nsf", cached_venv_path, target_venv_path])
    activate_this = os.path.join(target_venv_path, "bin", "activate_this.py")
    exec(open(activate_this).read(), {}, dict(__file__=activate_this)) # type: ignore # https://github.com/python/mypy/issues/1577

def do_setup_virtualenv(venv_path, requirements_file, virtualenv_args):
    # type: (str, str, List[str]) -> None

    # Setup Python virtualenv
    run(["sudo", "rm", "-rf", venv_path])
    run(["sudo", "mkdir", "-p", venv_path])
    run(["sudo", "chown", "{}:{}".format(os.getuid(), os.getgid()), venv_path])
    run(["virtualenv"] + virtualenv_args + [venv_path])

    # Switch current Python context to the virtualenv.
    activate_this = os.path.join(venv_path, "bin", "activate_this.py")
    exec(open(activate_this).read(), {}, dict(__file__=activate_this)) # type: ignore # https://github.com/python/mypy/issues/1577

    run(["pip", "install", "--upgrade", "pip"])
    run(["pip", "install", "--no-deps", "--requirement", requirements_file])
