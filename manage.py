#!/usr/bin/env python3
from __future__ import (print_function)
import os
import sys
import configparser
if sys.version_info <= (3, 0):
    print("Error: Zulip is a Python 3 project, and cannot be run with Python 2.")
    print("Use e.g. `/path/to/manage.py` not `python /path/to/manage.py`.")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import
from scripts.lib.zulip_tools import assert_not_running_as_root

if __name__ == "__main__":
    assert_not_running_as_root()

    config_file = configparser.RawConfigParser()
    config_file.read("/etc/zulip/zulip.conf")
    PRODUCTION = config_file.has_option('machine', 'deploy_type')
    HAS_SECRETS = os.access('/etc/zulip/zulip-secrets.conf', os.R_OK)

    if PRODUCTION and not HAS_SECRETS:
        # The best way to detect running manage.py as another user in
        # production before importing anything that would require that
        # access is to check for access to /etc/zulip/zulip.conf (in
        # which case it's a production server, not a dev environment)
        # and lack of access for /etc/zulip/zulip-secrets.conf (which
        # should be only readable by root and zulip)
        print("Error accessing Zulip secrets; manage.py in production must be run as the zulip user.")
        sys.exit(1)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
    from django.conf import settings
    from django.core.management import execute_from_command_line
    from django.core.management.base import CommandError
    from scripts.lib.zulip_tools import log_management_command

    log_management_command(" ".join(sys.argv), settings.MANAGEMENT_LOG_PATH)

    os.environ.setdefault("PYTHONSTARTUP", os.path.join(BASE_DIR, "scripts/lib/pythonrc.py"))
    if "--no-traceback" not in sys.argv and len(sys.argv) > 1:
        sys.argv.append("--traceback")
    try:
        execute_from_command_line(sys.argv)
    except CommandError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
