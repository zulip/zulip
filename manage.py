#!/usr/bin/env python3
from __future__ import absolute_import
from __future__ import print_function

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import

if __name__ == "__main__":
    if 'posix' in os.name and os.geteuid() == 0:
        from django.core.management.base import CommandError
        raise CommandError("manage.py should not be run as root.  Use `su zulip` to drop root.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
    os.environ.setdefault("PYTHONSTARTUP", os.path.join(BASE_DIR, "scripts/lib/pythonrc.py"))

    from django.conf import settings
    from django.core.management.base import CommandError
    from scripts.lib.zulip_tools import log_management_command

    log_management_command(" ".join(sys.argv), settings.MANAGEMENT_LOG_PATH)

    if "--no-traceback" not in sys.argv and len(sys.argv) > 1:
        sys.argv.append("--traceback")

    from django.core.management import execute_from_command_line

    try:
        execute_from_command_line(sys.argv)
    except CommandError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
