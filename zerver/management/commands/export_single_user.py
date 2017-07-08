from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser

import os
import shutil
import subprocess
import tempfile
import ujson

from zerver.lib.export import do_export_user
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Exports message data from a Zulip user

    This command exports the message history for a single Zulip user.

    Note that this only exports the user's message history and
    realm-public metadata needed to understand it; it does nothing
    with (for example) any bots owned by the user."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('email', metavar='<email>', type=str,
                            help="email of user to export")
        parser.add_argument('--output',
                            dest='output_dir',
                            action="store",
                            default=None,
                            help='Directory to write exported data to.')
        self.add_realm_args(parser)

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realm = self.get_realm(options)
        user_profile = self.get_user(options["email"], realm)

        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="/tmp/zulip-export-")
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        print("Exporting user %s" % (user_profile.email,))
        do_export_user(user_profile, output_dir)
        print("Finished exporting to %s; tarring" % (output_dir,))
        tarball_path = output_dir.rstrip('/') + '.tar.gz'
        subprocess.check_call(["tar", "--strip-components=1", "-czf", tarball_path, output_dir])
        print("Tarball written to %s" % (tarball_path,))
