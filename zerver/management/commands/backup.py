import os
import tempfile
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Any

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.management import ZulipBaseCommand
from scripts.lib.zulip_tools import run, TIMESTAMP_FORMAT


class Command(ZulipBaseCommand):
    # Fix support for multi-line usage strings
    def create_parser(self, *args: Any, **kwargs: Any) -> ArgumentParser:
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "output", default=None, nargs="?", help="Filename of output tarball"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        timestamp = timezone_now().strftime(TIMESTAMP_FORMAT)

        with tempfile.TemporaryDirectory(
            prefix="zulip-backup-%s-" % (timestamp,)
        ) as tmp:
            os.mkdir(os.path.join(tmp, "zulip-backup"))
            members = []

            if settings.DEVELOPMENT:
                os.symlink(
                    os.path.join(settings.DEPLOY_ROOT, "zproject"),
                    os.path.join(tmp, "zulip-backup", "zproject"),
                )
                members.append("zulip-backup/zproject/dev-secrets.conf")
            else:
                os.symlink("/etc/zulip", os.path.join(tmp, "zulip-backup", "settings"))
                members.append("zulip-backup/settings")

            db_name = settings.DATABASES["default"]["NAME"]
            db_dir = os.path.join(tmp, "zulip-backup", "database")
            run(["pg_dump", "--format=directory", db_name, "--file", db_dir])
            members.append("zulip-backup/database")

            if settings.LOCAL_UPLOADS_DIR is not None and os.path.exists(
                os.path.join(settings.DEPLOY_ROOT, settings.LOCAL_UPLOADS_DIR)
            ):
                os.symlink(
                    os.path.join(settings.DEPLOY_ROOT, settings.LOCAL_UPLOADS_DIR),
                    os.path.join(tmp, "zulip-backup", "uploads"),
                )
                members.append("zulip-backup/uploads")

            try:
                if options["output"] is None:
                    tarball_path = tempfile.NamedTemporaryFile(
                        prefix="zulip-backup-%s-" % (timestamp,),
                        suffix=".tar.gz",
                        delete=False,
                    ).name
                else:
                    tarball_path = options["output"]

                run(["tar", "-C", tmp, "-chzf", tarball_path, "--"] + members)
                print("Backup tarball written to %s" % (tarball_path,))
            except BaseException:
                if options["output"] is None:
                    os.unlink(tarball_path)
                raise
