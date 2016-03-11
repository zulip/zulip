#!/usr/bin/env python2.7
import os
import sys
import logging
import subprocess

if __name__ == "__main__":
    if 'posix' in os.name and os.geteuid() == 0:
        from django.core.management.base import CommandError
        raise CommandError("manage.py should not be run as root.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
    os.environ.setdefault("PYTHONSTARTUP", os.path.join(os.path.dirname(__file__), "scripts/lib/pythonrc.py"))

    from django.conf import settings

    logger = logging.getLogger("zulip.management")
    subprocess.check_call([os.path.join(os.path.dirname(__file__), "bin", "log-management-command"),
                           " ".join(sys.argv)])

    if "--no-traceback" not in sys.argv and len(sys.argv) > 1:
        sys.argv.append("--traceback")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
