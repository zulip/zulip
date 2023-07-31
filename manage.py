#!/usr/bin/env python3
import configparser
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
from scripts.lib.setup_path import setup_path

setup_path()

from django.core.management import ManagementUtility, get_commands
from django.core.management.color import color_style

from scripts.lib.zulip_tools import assert_not_running_as_root


def get_filtered_commands() -> Dict[str, str]:
    """Because Zulip uses management commands in production, `manage.py
    help` is a form of documentation for users. Here we exclude from
    that documentation built-in commands that are not constructive for
    end users or even Zulip developers to run.

    Ideally, we'd do further customization to display management
    commands with more organization in the help text, and also hide
    development-focused management commands in production.
    """
    all_commands = get_commands()
    documented_commands = dict()
    documented_apps = [
        # "auth" removed because its commands are not applicable to Zulip.
        # "contenttypes" removed because we don't use that subsystem, and
        #   even if we did.
        "django.core",
        "analytics",
        # "otp_static" removed because it's a 2FA internals detail.
        # "sessions" removed because it's just a cron job with a misleading
        #   name, since all it does is delete expired sessions.
        # "social_django" removed for similar reasons to sessions.
        # "staticfiles" removed because its commands are only usefully run when
        #   wrapped by Zulip tooling.
        # "two_factor" removed because it's a 2FA internals detail.
        "zerver",
        "zilencer",
    ]
    documented_command_subsets = {
        "django.core": {
            "changepassword",
            "dbshell",
            "makemigrations",
            "migrate",
            "shell",
            "showmigrations",
        },
    }
    for command, app in all_commands.items():
        if app not in documented_apps:
            continue
        if app in documented_command_subsets and command not in documented_command_subsets[app]:
            continue

        documented_commands[command] = app
    return documented_commands


class FilteredManagementUtility(ManagementUtility):
    """Replaces the main_help_text function of ManagementUtility with one
    that calls our get_filtered_commands(), rather than the default
    get_commands() function.

    All other change are just code style differences to pass the Zulip linter.
    """

    def main_help_text(self, commands_only: bool = False) -> str:
        """Return the script's main help text, as a string."""
        if commands_only:
            usage = sorted(get_filtered_commands())
        else:
            usage = [
                "",
                f"Type '{self.prog_name} help <subcommand>' for help on a specific subcommand.",
                "",
                "Available subcommands:",
            ]
            commands_dict = defaultdict(list)
            for name, app in get_filtered_commands().items():
                if app == "django.core":
                    app = "django"
                else:
                    app = app.rpartition(".")[-1]
                commands_dict[app].append(name)
            style = color_style()
            for app in sorted(commands_dict):
                usage.append("")
                usage.append(style.NOTICE(f"[{app}]"))
                usage.extend(f"    {name}" for name in sorted(commands_dict[app]))
            # Output an extra note if settings are not properly configured
            if self.settings_exception is not None:
                usage.append(
                    style.NOTICE(
                        "Note that only Django core commands are listed "
                        f"as settings are not properly configured (error: {self.settings_exception})."
                    )
                )

        return "\n".join(usage)


def execute_from_command_line(argv: Optional[List[str]] = None) -> None:
    """Run a FilteredManagementUtility."""
    utility = FilteredManagementUtility(argv)
    utility.execute()


if __name__ == "__main__":
    assert_not_running_as_root()

    config_file = configparser.RawConfigParser()
    config_file.read("/etc/zulip/zulip.conf")
    PRODUCTION = config_file.has_option("machine", "deploy_type")
    HAS_SECRETS = os.access("/etc/zulip/zulip-secrets.conf", os.R_OK)

    if PRODUCTION and not HAS_SECRETS:
        # The best way to detect running manage.py as another user in
        # production before importing anything that would require that
        # access is to check for access to /etc/zulip/zulip.conf (in
        # which case it's a production server, not a dev environment)
        # and lack of access for /etc/zulip/zulip-secrets.conf (which
        # should be only readable by root and zulip)
        print(
            "Error accessing Zulip secrets; manage.py in production must be run as the zulip user."
        )
        sys.exit(1)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
    from django.conf import settings
    from django.core.management.base import CommandError

    from scripts.lib.zulip_tools import log_management_command

    log_management_command(sys.argv, settings.MANAGEMENT_LOG_PATH)

    os.environ.setdefault("PYTHONSTARTUP", os.path.join(BASE_DIR, "scripts/lib/pythonrc.py"))
    if "--no-traceback" not in sys.argv and len(sys.argv) > 1:
        sys.argv.append("--traceback")
    try:
        execute_from_command_line(sys.argv)
    except CommandError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
