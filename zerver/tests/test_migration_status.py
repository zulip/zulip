from zerver.lib.migration_status import (
    STALE_MIGRATIONS,
    AppMigrations,
    get_migration_status,
    parse_migration_status,
)
from zerver.lib.test_classes import ZulipTestCase


class MigrationStatusTests(ZulipTestCase):
    def test_parse_migration_status(self) -> None:
        showmigrations_sample = """
analytics
 [X] 0001_squashed_0021_alter_fillstate_id (21 squashed migrations)
auth
 [ ] 0012_alter_user_first_name_max_length
zerver
 [-] 0015_alter_confirmation_object_id
two_factor
 (no migrations)
"""
        app_migrations = parse_migration_status(showmigrations_sample)
        expected: AppMigrations = {
            "analytics": ["[X] 0001_squashed_0021_alter_fillstate_id (21 squashed migrations)"],
            "auth": ["[ ] 0012_alter_user_first_name_max_length"],
            "zerver": ["[-] 0015_alter_confirmation_object_id"],
            "two_factor": ["(no migrations)"],
        }
        self.assertDictEqual(app_migrations, expected)

        # Run one with the real showmigrations. A more thorough tests of these
        # functions are done in the test_import_export.py as part of the import-
        # export suite.
        showmigrations = get_migration_status(app_label="zerver")
        app_migrations = parse_migration_status(showmigrations)
        zerver_migrations = app_migrations.get("zerver")
        self.assertIsNotNone(zerver_migrations)
        self.assertNotEqual(zerver_migrations, [])

    def test_parse_stale_migration_status(self) -> None:
        assert ("guardian", "0001_initial") in STALE_MIGRATIONS
        showmigrations_sample = """
analytics
 [X] 0001_squashed_0021_alter_fillstate_id (21 squashed migrations)
auth
 [ ] 0012_alter_user_first_name_max_length
zerver
 [-] 0015_alter_confirmation_object_id
two_factor
 (no migrations)
guardian
 [X] 0001_initial
"""
        app_migrations = parse_migration_status(showmigrations_sample)
        expected: AppMigrations = {
            "analytics": ["[X] 0001_squashed_0021_alter_fillstate_id (21 squashed migrations)"],
            "auth": ["[ ] 0012_alter_user_first_name_max_length"],
            "zerver": ["[-] 0015_alter_confirmation_object_id"],
            "two_factor": ["(no migrations)"],
        }
        self.assertDictEqual(app_migrations, expected)
