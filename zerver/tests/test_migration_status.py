from unittest.mock import patch

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from zerver.lib.migration_status import (
    STALE_MIGRATIONS,
    AppMigrations,
    get_migration_status,
    parse_migration_status,
)
from zerver.lib.test_classes import ZulipTestCase


class MigrationStatusTests(ZulipTestCase):
    def parse_showmigrations(
        self,
        migration_status_print: str,
        stale_migrations: list[tuple[str, str]] = STALE_MIGRATIONS,
    ) -> AppMigrations:
        """
        Parses the output of Django's `showmigrations` into a data structure
        identical to the output `parse_migration_status` generates.

        Makes sure this accurately parses the output of `showmigrations`.
        """
        lines = migration_status_print.strip().split("\n")
        migrations_dict: AppMigrations = {}
        current_app = None
        line_prefix = ("[X]", "[ ]", "[-]", "(no migrations)")

        stale_migrations_dict: dict[str, list[str]] = {}
        for app, migration in stale_migrations:
            if app not in stale_migrations_dict:
                stale_migrations_dict[app] = []
            stale_migrations_dict[app].append(migration)

        for line in lines:
            line = line.strip()
            if not line.startswith(line_prefix) and line:
                current_app = line
                migrations_dict[current_app] = []
            elif line.startswith(line_prefix):
                assert current_app is not None
                apps_stale_migrations = stale_migrations_dict.get(current_app)
                if (
                    apps_stale_migrations is not None
                    and line != "(no migrations)"
                    and line[4:] in apps_stale_migrations
                ):
                    continue
                migrations_dict[current_app].append(line)

        # Installed apps that have no migrations and we still use will have
        # "(no migrations)" as its only "migrations" list. Ones that just
        # have [] means it's just a left over stale app we can clean up.
        return {app: migrations for app, migrations in migrations_dict.items() if migrations != []}

    def test_parse_showmigrations(self) -> None:
        """
        This function tests a helper test function `parse_showmigrations`.
        It is critical that this correctly checks the behavior of
        `parse_showmigrations`. Make sure it is accurately parsing the
        output of `showmigrations`.
        """
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
        app_migrations = self.parse_showmigrations(showmigrations_sample)
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
        app_migrations = self.parse_showmigrations(showmigrations)
        zerver_migrations = app_migrations.get("zerver")
        self.assertIsNotNone(zerver_migrations)
        self.assertNotEqual(zerver_migrations, [])

    def test_parse_showmigrations_filters_out_stale_migrations(self) -> None:
        """
        This function tests a helper test function `parse_showmigrations`.
        It is critical that this correctly checks the behavior of
        `parse_showmigrations`. Make sure it is accurately parsing the
        output of `showmigrations`.
        """
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
        app_migrations = self.parse_showmigrations(showmigrations_sample)
        expected: AppMigrations = {
            "analytics": ["[X] 0001_squashed_0021_alter_fillstate_id (21 squashed migrations)"],
            "auth": ["[ ] 0012_alter_user_first_name_max_length"],
            "zerver": ["[-] 0015_alter_confirmation_object_id"],
            "two_factor": ["(no migrations)"],
        }
        self.assertDictEqual(app_migrations, expected)

    def test_parse_migration_status(self) -> None:
        """
        This test asserts that the algorithm in `parse_migration_status` is the same
        as Django's `showmigrations`.
        """
        migration_status_print = get_migration_status()
        parsed_showmigrations = self.parse_showmigrations(migration_status_print)
        migration_status_dict = parse_migration_status()
        self.assertDictEqual(migration_status_dict, parsed_showmigrations)

    def test_applied_but_not_recorded(self) -> None:
        # Mock applied_migrations() to simulate empty recorded_migrations.
        with patch(
            "zerver.lib.migration_status.MigrationRecorder.applied_migrations",
        ):
            result = parse_migration_status()
            self.assertIn("[-] 0010_alter_group_name_max_length", result["auth"])

    def test_generate_unapplied_migration(self) -> None:
        recorder = MigrationRecorder(connection)
        recorder.record_unapplied("auth", "0010_alter_group_name_max_length")
        result = parse_migration_status()
        self.assertIn("[ ] 0010_alter_group_name_max_length", result["auth"])
