from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

import os
import shutil
import subprocess
import tempfile
import ujson

from zerver.lib.export import do_export_user
from zerver.models import UserProfile, get_user_profile_by_email

class Command(BaseCommand):
    help = """Exports message data from a Zulip user

    This command exports the message history for a single Zulip user.

    Note that this only exports the user's message history and
    realm-public metadata needed to understand it; it does nothing
    with (for example) any bots owned by the user."""

    def add_arguments(self, parser):
        parser.add_argument('email', metavar='<email>', type=str,
                            help="email of user to export")
        parser.add_argument('--output',
                            dest='output_dir',
                            action="store",
                            default=None,
                            help='Directory to write exported data to.')

    def handle(self, *args, **options):
        try:
            user_profile = get_user_profile_by_email(options["email"])
        except UserProfile.DoesNotExist:
            raise CommandError("No such user.")

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
