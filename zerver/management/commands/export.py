from __future__ import absolute_import
from __future__ import print_function

from argparse import RawTextHelpFormatter
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

import os
import shutil
import subprocess
import tempfile
import ujson

from zerver.lib.export import (
    do_export_realm, do_write_stats_file_for_realm_export
)
from zerver.models import get_realm

class Command(BaseCommand):
    help = """Exports all data from a Zulip realm

    This command exports all significant data from a Zulip realm.  The
    result can be imported using the `./manage.py import` command.

    Things that are exported:
    * All user-accessible data in the Zulip database (Messages,
      Streams, UserMessages, RealmEmoji, etc.)
    * Copies of all uploaded files and avatar images along with
      metadata needed to restore them even in the ab

    Things that are not exported:
    * Confirmation, MitUser, and PreregistrationUser (transient tables)
    * Sessions (everyone will need to login again post-export)
    * Users' passwords and API keys (users will need to use SSO or reset password)
    * Mobile tokens for APNS/GCM (users will need to reconnect their mobile devices)
    * ScheduledJob (Not relevant on a new server)
    * Referral (Unused)
    * Deployment (Unused)
    * third_party_api_results cache (this means rerending all old
      messages could be expensive)

    Things that will break as a result of the export:
    * Passwords will not be transferred.  They will all need to go
      through the password reset flow to obtain a new password (unless
      they intend to only use e.g. Google Auth).
    * Users will need to logout and re-login to the Zulip desktop and
      mobile apps.  The apps now all have an option on the login page
      where you can specify which Zulip server to use; your users
      should enter <domain name>.
    * All bots will stop working since they will be pointing to the
      wrong server URL, and all users' API keys have been rotated as
      part of the migration.  So to re-enable your integrations, you
      will need to direct your integrations at the new server.
      Usually this means updating the URL and the bots' API keys.  You
      can see a list of all the bots that have been configured for
      your realm on the `/#administration` page, and use that list to
      make sure you migrate them all.

    The proper procedure for using this to export a realm is as follows:

    * Use `./manage.py deactivate_realm` to deactivate the realm, so
      nothing happens in the realm being exported during the export
      process.

    * Use `./manage.py export` to export the realm, producing a data
      tarball.

    * Transfer the tarball to the new server and unpack it.

    * Use `./manage.py import` to import the realm

    * Use `./manage.py reactivate_realm` to reactivate the realm, so
      users can login again.

    * Inform the users about the things broken above.

    We recommend testing by exporting without having deactivated the
    realm first, to make sure you have the procedure right and
    minimize downtime.

    Performance: In one test, the tool exported a realm with hundreds
    of users and ~1M messages of history with --threads=1 in about 3
    hours of serial runtime (goes down to ~50m with --threads=6 on a
    machine with 8 CPUs).  Importing that same data set took about 30
    minutes.  But this will vary a lot depending on the average number
    of recipients of messages in the realm, hardware, etc."""

    # Fix support for multi-line usage
    def create_parser(self, *args, **kwargs):
        parser = super(Command, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument('realm', metavar='<realm>', type=str,
                            help="realm to export")
        parser.add_argument('--output',
                            dest='output_dir',
                            action="store",
                            default=None,
                            help='Directory to write exported data to.')
        parser.add_argument('--threads',
                            dest='threads',
                            action="store",
                            default=6,
                            help='Threads to use in exporting UserMessage objects in parallel')

    def handle(self, *args, **options):
        try:
            realm = get_realm(options["realm"])
        except ValidationError:
            raise CommandError("No such realm.")

        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="/tmp/zulip-export-")
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        print("Exporting realm %s" % (realm.domain,))
        num_threads = int(options['threads'])
        if num_threads < 1:
            raise CommandError('You must have at least one thread.')

        do_export_realm(realm, output_dir, threads=num_threads)
        print("Finished exporting to %s; tarring" % (output_dir,))

        do_write_stats_file_for_realm_export(output_dir)

        tarball_path = output_dir.rstrip('/') + '.tar.gz'
        os.chdir(os.path.dirname(output_dir))
        subprocess.check_call(["tar", "-czf", tarball_path, os.path.basename(output_dir)])
        print("Tarball written to %s" % (tarball_path,))
