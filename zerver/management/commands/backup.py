
import os
import shutil
import subprocess
import tempfile
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError
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
        parser.add_argument('--output',
                            dest='output_dir',
                            action="store",
                            default=None,
                            help='Directory to write backup tarball to.')

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            timestamp = timezone_now().strftime(TIMESTAMP_FORMAT)
            output_dir = tempfile.mkdtemp(prefix="/tmp/zulip-backup-%s-" % (timestamp,))
        else:
            output_dir = os.path.realpath(os.path.expanduser(output_dir))

        os.makedirs(output_dir, exist_ok=True)

        DATABASES = settings.DATABASES['default']
        postgres_dir = os.path.join(output_dir, "database")
        run(["pg_dump", "--format=directory", DATABASES['NAME'],
             "--file", postgres_dir])

        if settings.LOCAL_UPLOADS_DIR is not None:
            uploads_tarball = os.path.join(output_dir, "files.tar.gz")
            run(["tar", "-czf", uploads_tarball,
                 '-C', settings.LOCAL_UPLOADS_DIR, '.'])

        settings_path = "/etc/zulip"
        if settings.DEVELOPMENT:
            settings_path = os.path.join(settings.DEPLOY_ROOT, "zproject")
        settings_tarball = os.path.join(output_dir, "settings.tar.gz")
        run(["tar", "-C", settings_path, "-czf", settings_tarball, '.'])

        tarball_path = output_dir.rstrip('/') + '.tar.gz'
        os.chdir(os.path.dirname(output_dir))
        subprocess.check_call(["tar", "-czf", tarball_path, os.path.basename(output_dir)])
        print("Backup tarball written to %s" % (tarball_path,))
