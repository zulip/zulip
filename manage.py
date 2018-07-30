#!/usr/bin/env python3
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import

if __name__ == "__main__":
    if 'posix' in os.name and os.geteuid() == 0:
        print("manage.py should not be run as root.  Use `su zulip` to drop root.")
        sys.exit(1)
    if (os.access('/etc/zulip/zulip.conf', os.R_OK) and not
            os.access('/etc/zulip/zulip-secrets.conf', os.R_OK)):
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
