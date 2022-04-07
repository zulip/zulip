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

# Ignore django-guardian, which we installed until 1.7.0~3134
missing.discard(("guardian", "0001_initial"))

# Ignore django.contrib.sites, which we installed until 2.0.0-rc1~984.
missing.discard(("sites", "0001_initial"))
missing.discard(("sites", "0002_alter_domain_unique"))

# These migrations were squashed into 0001, in 6fbddf578a6e through
# a21f2d771553, 1.7.0~3135.
missing.difference_update(
    [
        ("zerver", "0002_django_1_8"),
        ("zerver", "0003_custom_indexes"),
        ("zerver", "0004_userprofile_left_side_userlist"),
        ("zerver", "0005_auto_20150920_1340"),
        ("zerver", "0006_zerver_userprofile_email_upper_idx"),
        ("zerver", "0007_userprofile_is_bot_active_indexes"),
        ("zerver", "0008_preregistrationuser_upper_email_idx"),
        ("zerver", "0009_add_missing_migrations"),
        ("zerver", "0010_delete_streamcolor"),
        ("zerver", "0011_remove_guardian"),
        ("zerver", "0012_remove_appledevicetoken"),
        ("zerver", "0013_realmemoji"),
        ("zerver", "0014_realm_emoji_url_length"),
        ("zerver", "0015_attachment"),
        ("zerver", "0016_realm_create_stream_by_admins_only"),
        ("zerver", "0017_userprofile_bot_type"),
        ("zerver", "0018_realm_emoji_message"),
        ("zerver", "0019_preregistrationuser_realm_creation"),
        ("zerver", "0020_add_tracking_attachment"),
        ("zerver", "0021_migrate_attachment_data"),
        ("zerver", "0022_subscription_pin_to_top"),
        ("zerver", "0023_userprofile_default_language"),
        ("zerver", "0024_realm_allow_message_editing"),
        ("zerver", "0025_realm_message_content_edit_limit"),
        ("zerver", "0026_delete_mituser"),
        ("zerver", "0027_realm_default_language"),
        ("zerver", "0028_userprofile_tos_version"),
    ]
)

# This migration was in python-social-auth, and was mistakenly removed
# from its `replaces` in
# https://github.com/python-social-auth/social-app-django/pull/25
missing.discard(("default", "0005_auto_20160727_2333"))

for key, migration in loader.disk_migrations.items():
    missing.discard(key)
    missing.difference_update(migration.replaces)
if not missing:
    sys.exit(0)

print("Migrations which are currently applied, but missing in the new version:")
for app, migration_name in sorted(missing):
    print(f"  {app} - {migration_name}")

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
