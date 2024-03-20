import os
import re
import tempfile
from argparse import ArgumentParser, RawTextHelpFormatter
from glob import glob
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from django.db import connection
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from scripts.lib.zulip_tools import TIMESTAMP_FORMAT, parse_os_release, run
from version import ZULIP_VERSION
from zerver.lib.management import ZulipBaseCommand
from zerver.logging_handlers import try_git_describe


class Command(ZulipBaseCommand):
    # Fix support for multi-line usage strings
    @override
    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--output", help="Filename of output tarball")
        parser.add_argument("--skip-db", action="store_true", help="Skip database backup")
        parser.add_argument("--skip-uploads", action="store_true", help="Skip uploads backup")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        timestamp = timezone_now().strftime(TIMESTAMP_FORMAT)
        with tempfile.TemporaryDirectory(
            prefix=f"zulip-backup-{timestamp}-",
        ) as tmp:
            os.mkdir(os.path.join(tmp, "zulip-backup"))
            members = []
            paths = []

            with open(os.path.join(tmp, "zulip-backup", "zulip-version"), "w") as f:
                print(ZULIP_VERSION, file=f)
                git = try_git_describe()
                if git:
                    print(git, file=f)
            members.append("zulip-backup/zulip-version")

            with open(os.path.join(tmp, "zulip-backup", "os-version"), "w") as f:
                print(
                    "{ID} {VERSION_ID}".format(**parse_os_release()),
                    file=f,
                )
            members.append("zulip-backup/os-version")

            with open(os.path.join(tmp, "zulip-backup", "postgres-version"), "w") as f:
                pg_server_version = connection.cursor().connection.server_version
                major_pg_version = pg_server_version // 10000
                print(pg_server_version, file=f)
            members.append("zulip-backup/postgres-version")

            if settings.DEVELOPMENT:
                members.append(
                    os.path.join(settings.DEPLOY_ROOT, "zproject", "dev-secrets.conf"),
                )
                paths.append(
                    ("zproject", os.path.join(settings.DEPLOY_ROOT, "zproject")),
                )
            else:
                members.append("/etc/zulip")
                paths.append(("settings", "/etc/zulip"))

            if not options["skip_db"]:
                # Find the version of of the pg_dump client to use.
                # We must not use a pg_dump client binary which is
                # newer than the server's version, since binary
                # pg_dump output is not always backwards-compatible.
                pg_dump_versions = []
                pg_dump_binaries = glob("/usr/lib/postgresql/*/bin/pg_dump")
                for pg_dump_binary in pg_dump_binaries:
                    version_string = pg_dump_binary.split("/")[4]
                    if version_string.isdecimal() and int(version_string) <= major_pg_version:
                        pg_dump_versions.append(int(version_string))

                if not pg_dump_versions:
                    raise CommandError(
                        "Could not find a valid pg_dump version which is compatible with server version {}: found {}".format(
                            major_pg_version, pg_dump_binaries
                        )
                    )
                pg_dump_versions.sort(reverse=True)
                pg_dump_command = [
                    f"/usr/lib/postgresql/{pg_dump_versions[0]}/bin/pg_dump",
                    "--format=directory",
                    "--file=" + os.path.join(tmp, "zulip-backup", "database"),
                    "--username=" + settings.DATABASES["default"]["USER"],
                    "--dbname=" + settings.DATABASES["default"]["NAME"],
                    "--no-password",
                ]
                if settings.DATABASES["default"]["HOST"] != "":
                    pg_dump_command += ["--host=" + settings.DATABASES["default"]["HOST"]]
                if settings.DATABASES["default"]["PORT"] != "":
                    pg_dump_command += ["--port=" + settings.DATABASES["default"]["PORT"]]

                os.environ["PGPASSWORD"] = settings.DATABASES["default"]["PASSWORD"]

                run(
                    pg_dump_command,
                    cwd=tmp,
                )
                members.append("zulip-backup/database")

            if (
                not options["skip_uploads"]
                and settings.LOCAL_UPLOADS_DIR is not None
                and os.path.exists(
                    os.path.join(settings.DEPLOY_ROOT, settings.LOCAL_UPLOADS_DIR),
                )
            ):
                members.append(
                    os.path.join(settings.DEPLOY_ROOT, settings.LOCAL_UPLOADS_DIR),
                )
                paths.append(
                    (
                        "uploads",
                        os.path.join(settings.DEPLOY_ROOT, settings.LOCAL_UPLOADS_DIR),
                    ),
                )

            assert not any("|" in name or "|" in path for name, path in paths)
            transform_args = [
                r"--transform=s|^{}(/.*)?$|zulip-backup/{}\1|x".format(
                    re.escape(path),
                    name.replace("\\", r"\\"),
                )
                for name, path in paths
            ]

            try:
                if options["output"] is None:
                    tarball_path = tempfile.NamedTemporaryFile(
                        prefix=f"zulip-backup-{timestamp}-",
                        suffix=".tar.gz",
                        delete=False,
                    ).name
                else:
                    tarball_path = options["output"]

                run(
                    [
                        "tar",
                        f"--directory={tmp}",
                        "-cPzf",
                        tarball_path,
                        *transform_args,
                        "--",
                        *members,
                    ]
                )
                print(f"Backup tarball written to {tarball_path}")
            except BaseException:
                if options["output"] is None:
                    os.unlink(tarball_path)
                raise
