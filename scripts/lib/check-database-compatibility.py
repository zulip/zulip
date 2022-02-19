#!/usr/bin/env python3
import logging
import os
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ZULIP_PATH)
from scripts.lib.setup_path import setup_path
from scripts.lib.zulip_tools import DEPLOYMENTS_DIR, assert_not_running_as_root, parse_version_from
from version import ZULIP_VERSION as new_version

assert_not_running_as_root()
setup_path()
os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"

import django
from django.db import connection
from django.db.migrations.loader import MigrationLoader

django.setup()
loader = MigrationLoader(connection)
missing = set(loader.applied_migrations)
for key, migration in loader.disk_migrations.items():
    missing.discard(key)
    missing.difference_update(migration.replaces)
if not missing:
    sys.exit(0)

current_version = parse_version_from(os.path.join(DEPLOYMENTS_DIR, "current"))
logging.error(
    "This is not an upgrade -- the current deployment (version %s) "
    "contains %s database migrations which %s (version %s) does not.",
    current_version,
    len(missing),
    ZULIP_PATH,
    new_version,
)
sys.exit(1)
