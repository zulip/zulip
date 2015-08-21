from __future__ import absolute_import

import os
import sys
import datetime
import tempfile
import traceback
import ujson

from django.core.management.base import BaseCommand
from zerver.retention_policy     import should_expunge_from_log

now = datetime.datetime.now()

def copy_retained_messages(infile, outfile):
    """Copy messages from infile to outfile which should be retained
       according to policy."""
    for ln in infile:
        msg = ujson.loads(ln)
        if not should_expunge_from_log(msg, now):
            outfile.write(ln)

def expunge(filename):
    """Expunge entries from the named log file, in place."""

    # We don't use the 'with' statement for tmpfile because we need to
    # either move it or delete it, depending on success or failure.
    #
    # We create it in the same directory as infile for two reasons:
    #
    #   - It makes it more likely we will notice leftover temp files
    #
    #   - It ensures that they are on the same filesystem, so we can
    #     use atomic os.rename().
    #
    tmpfile = tempfile.NamedTemporaryFile(
        mode   = 'wb',
        dir    = os.path.dirname(filename),
        delete = False)

    try:
        try:
            with open(filename, 'rb') as infile:
                copy_retained_messages(infile, tmpfile)
        finally:
            tmpfile.close()

        os.rename(tmpfile.name, filename)
    except:
        os.unlink(tmpfile.name)
        raise

class Command(BaseCommand):
    help = ('Expunge old entries from one or more log files, '
            + 'according to the retention policy.')

    def add_arguments(self, parser):
        parser.add_argument('log_files', metavar='<log file>', type=str, nargs='*',
                            help='file to expunge entries from')

    def handle(self, *args, **options):
        if len(options['log_files']) == 0:
            print >>sys.stderr, 'WARNING: No log files specified; doing nothing.'

        for infile in options['log_files']:
            try:
                expunge(infile)
            except KeyboardInterrupt:
                raise
            except:
                print >>sys.stderr, 'WARNING: Could not expunge from', infile
                traceback.print_exc()
