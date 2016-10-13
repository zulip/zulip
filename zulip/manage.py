#!/usr/bin/env python
import os
import sys
import logging
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import

if __name__ == "__main__":
    if 'posix' in os.name and os.geteuid() == 0:
        from django.core.management.base import CommandError
        raise CommandError("manage.py should not be run as root.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
    os.environ.setdefault("PYTHONSTARTUP", os.path.join(BASE_DIR, "scripts/lib/pythonrc.py"))

    from django.conf import settings

    logger = logging.getLogger("zulip.management")
    subprocess.check_call([os.path.join(BASE_DIR, "scripts", "lib", "log-management-command"),
                           " ".join(sys.argv)])

    if "--no-traceback" not in sys.argv and len(sys.argv) > 1:
        sys.argv.append("--traceback")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
