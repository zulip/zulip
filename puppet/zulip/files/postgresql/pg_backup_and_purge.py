#!/usr/bin/env python

from __future__ import print_function

import sys
import glob
import subprocess
import sys
import logging
import dateutil.parser
import pytz
from datetime import datetime, timedelta
if False: from typing import List

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run(args, dry_run=False):
    # type: (List[str], bool) -> str
    if dry_run:
        print("Would have run: " + " ".join(args))
        return ""

    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.returncode:
        logger.error("Could not invoke %s\nstdout: %s\nstderror: %s"
                     % (args[0], stdout, stderr))
        sys.exit(1)
    return stdout

# Only run if we're the master
if run(['psql', '-t', '-c', 'select pg_is_in_recovery()']).strip() != 'f':
    sys.exit(0)

pg_data_paths = glob.glob('/var/lib/postgresql/*/main')
if len(pg_data_paths) != 1:
    print("Postgres installation is not unique: %s" % (pg_data_paths,))
    sys.exit(1)
pg_data_path = pg_data_paths[0]
run(['env-wal-e', 'backup-push', pg_data_path])

now = datetime.now(tz=pytz.utc)
with open('/var/lib/nagios_state/last_postgres_backup', 'w') as f:
    f.write(now.isoformat())
    f.write("\n")

backups = {} # type: Dict[datetime, str]
lines = run(['env-wal-e', 'backup-list']).split("\n")
for line in lines[1:]:
    if line:
        backup_name, date_str, _, _ = line.split()
        backups[dateutil.parser.parse(date_str)] = backup_name

one_month_ago = now - timedelta(days=30)
for date in sorted(backups.keys(), reverse=True):
    if date < one_month_ago:
        run(['env-wal-e', 'delete', '--confirm', 'before', backups[date]])
        # Because we're going from most recent to least recent, we
        # only have to do one delete operation
        break
