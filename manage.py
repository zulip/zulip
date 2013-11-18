#!/usr/bin/env python
import os
import sys
import logging
import subprocess

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")

    from django.conf import settings

    logger = logging.getLogger("zulip.management")
    subprocess.check_call([os.path.join(os.path.dirname(__file__), "bin", "log-management-command"),
                           " ".join(sys.argv)])

    if "--no-traceback" not in sys.argv and len(sys.argv) > 1:
        sys.argv.append("--traceback")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
