import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, ProgrammingError, connection, connections
from django.db.utils import OperationalError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from scripts.lib.zulip_tools import (
    TEMPLATE_DATABASE_DIR,
    get_dev_uuid_var_path,
    is_digest_obsolete,
    run,
    write_new_digest,
)

BACKEND_DATABASE_TEMPLATE = "zulip_test_template"
UUID_VAR_DIR = get_dev_uuid_var_path()

IMPORTANT_FILES = [
    "zilencer/management/commands/populate_db.py",
    "zerver/actions/create_realm.py",
    "zerver/lib/bulk_create.py",
    "zerver/lib/generate_test_data.py",
    "zerver/lib/server_initialization.py",
    "tools/setup/postgresql-init-test-db",
    "tools/setup/postgresql-init-dev-db",
    "zerver/migrations/0258_enable_online_push_notifications_default.py",
]

VERBOSE_MESSAGE_ABOUT_HASH_TRANSITION = """
    NOTE!!!!

    We are rebuilding your database for a one-time transition.

    We have a hashing scheme that we use to detect whether any
    important files used in the construction of the database
    have changed.

    We are changing that scheme so it only uses one file
    instead of a directory of files.

    In order to prevent errors due to this transition, we are
    doing a one-time rebuild of your database.  This should
    be the last time this happens (for this particular reason,
    at least), unless you go back to older branches.

"""


def migration_paths() -> list[str]:
    return [
        *glob.glob("*/migrations/*.py"),
        "uv.lock",
    ]


class Database:
    def __init__(self, platform: str, database_name: str, settings: str) -> None:
        self.database_name = database_name
        self.settings = settings
        self.digest_name = "db_files_hash_for_" + platform
        self.migration_status_file = "migration_status_" + platform
        self.migration_status_path = os.path.join(
            UUID_VAR_DIR,
            self.migration_status_file,
        )
        self.migration_digest_file = "migrations_hash_" + database_name

    def important_settings(self) -> list[str]:
        def get(setting_name: str) -> str:
            value = getattr(settings, setting_name, {})
            return json.dumps(value, sort_keys=True)

        return [
            get("LOCAL_DATABASE_PASSWORD"),
            get("INTERNAL_BOTS"),
            get("REALM_INTERNAL_BOTS"),
            get("DISABLED_REALM_INTERNAL_BOTS"),
        ]

    def run_db_migrations(self) -> None:
        # We shell out to `manage.py` and pass `DJANGO_SETTINGS_MODULE` on
        # the command line rather than just calling the migration
        # functions, because Django doesn't support changing settings like
        # what the database is as runtime.
        # Also we export ZULIP_DB_NAME which is ignored by dev platform but
        # recognised by test platform and used to migrate correct db.
        manage_py = [
            "env",
            "DJANGO_SETTINGS_MODULE=" + self.settings,
            "ZULIP_DB_NAME=" + self.database_name,
            "./manage.py",
        ]

        run([*manage_py, "migrate", "--skip-checks", "--no-input"])

        run(
            [
                *manage_py,
                "get_migration_status",
                "--skip-checks",
                "--output=" + self.migration_status_file,
            ]
        )

    def what_to_do_with_migrations(self) -> str:
        from zerver.lib.migration_status import get_migration_status

        status_fn = self.migration_status_path
        settings = self.settings

        if not os.path.exists(status_fn):
            return "scrap"

        with open(status_fn) as f:
            previous_migration_status = f.read()

        current_migration_status = get_migration_status(settings=settings)
        connections.close_all()
        all_curr_migrations = extract_migrations_as_list(current_migration_status)
        all_prev_migrations = extract_migrations_as_list(previous_migration_status)

        if len(all_curr_migrations) < len(all_prev_migrations):
            return "scrap"

        for migration in all_prev_migrations:
            if migration not in all_curr_migrations:
                return "scrap"

        if len(all_curr_migrations) == len(all_prev_migrations):
            return "migrations_are_latest"

        return "migrate"

    def database_exists(self) -> bool:
        try:
            connection = connections[DEFAULT_DB_ALIAS]

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 from pg_database WHERE datname=%s;",
                    [self.database_name],
                )
                return_value = bool(cursor.fetchone())
            connections.close_all()
            return return_value
        except OperationalError:
            return False

    def files_or_settings_have_changed(self) -> bool:
        database_name = self.database_name

        # Deal with legacy hash files.  We can kill off this code when
        # enough time has passed since April 2020 that we're not
        # worried about anomalies doing `git bisect`--probably a few
        # months is sufficient.
        legacy_status_dir = os.path.join(UUID_VAR_DIR, database_name + "_db_status")
        if os.path.exists(legacy_status_dir):
            print(VERBOSE_MESSAGE_ABOUT_HASH_TRANSITION)

            # Remove the old digest for several reasons:
            #   - tidiness
            #   - preventing false positives if you bisect
            #   - make this only a one-time headache (generally)
            shutil.rmtree(legacy_status_dir)

            # Return True to force a one-time rebuild.
            return True

        return is_digest_obsolete(
            self.digest_name,
            IMPORTANT_FILES,
            self.important_settings(),
        )

    def template_status(self) -> str:
        # This function returns a status string specifying the type of
        # state the template db is in and thus the kind of action required.
        if not self.database_exists():
            # TODO: It's possible that `database_exists` will
            #       return `False` even though the database
            #       exists, but we just have the wrong password,
            #       probably due to changing the secrets file.
            #
            #       The only problem this causes is that we waste
            #       some time rebuilding the whole database, but
            #       it's better to err on that side, generally.
            return "needs_rebuild"

        if self.files_or_settings_have_changed():
            return "needs_rebuild"

        # Here we hash and compare our migration files before doing
        # the work of seeing what to do with them; if there are no
        # changes, we can safely assume we don't need to run
        # migrations without spending a few 100ms parsing all the
        # Python migration code.
        if not self.is_migration_digest_obsolete():
            return "current"

        """
        NOTE:
            We immediately update the digest, assuming our
            callers will do what it takes to run the migrations.

            Ideally our callers would just do it themselves
            AFTER the migrations actually succeeded, but the
            caller codepaths are kind of complicated here.
        """
        self.write_new_migration_digest()

        migration_op = self.what_to_do_with_migrations()
        if migration_op == "scrap":
            return "needs_rebuild"

        if migration_op == "migrate":
            return "run_migrations"

        return "current"

    def is_migration_digest_obsolete(self) -> bool:
        return is_digest_obsolete(
            self.migration_digest_file,
            migration_paths(),
        )

    def write_new_migration_digest(self) -> None:
        write_new_digest(
            self.migration_digest_file,
            migration_paths(),
        )

    def write_new_db_digest(self) -> None:
        write_new_digest(
            self.digest_name,
            IMPORTANT_FILES,
            self.important_settings(),
        )


DEV_DATABASE = Database(
    platform="dev",
    database_name="zulip",
    settings="zproject.settings",
)

TEST_DATABASE = Database(
    platform="test",
    database_name="zulip_test_template",
    settings="zproject.test_settings",
)


def update_test_databases_if_required(rebuild_test_database: bool = False) -> None:
    """Checks whether the zulip_test_template database template, is
    consistent with our database migrations; if not, it updates it
    in the fastest way possible:

    * If all we need to do is add some migrations, just runs those
      migrations on the template database.
    * Otherwise, we rebuild the test template database from scratch.

    The default behavior is sufficient for the `test-backend` use
    case, where the test runner code will clone directly from the
    template database.

    The `rebuild_test_database` option (used by our frontend and API
    tests) asks us to drop and re-cloning the zulip_test database from
    the template so those test suites can run with a fresh copy.

    """
    test_template_db_status = TEST_DATABASE.template_status()

    if test_template_db_status == "needs_rebuild":
        run(["tools/rebuild-test-database"])
        TEST_DATABASE.write_new_db_digest()
        return

    if test_template_db_status == "run_migrations":
        TEST_DATABASE.run_db_migrations()
        run(["tools/setup/generate-fixtures"])
        return

    if rebuild_test_database:
        run(["tools/setup/generate-fixtures"])


def extract_migrations_as_list(migration_status: str) -> list[str]:
    MIGRATIONS_RE = re.compile(r"\[[X| ]\] (\d+_.+)\n")
    return MIGRATIONS_RE.findall(migration_status)


def destroy_leaked_test_databases(expiry_time: int = 60 * 60) -> int:
    """The logic in zerver/lib/test_runner.py tries to delete all the
    temporary test databases generated by test-backend threads, but it
    cannot guarantee it handles all race conditions correctly.  This
    is a catch-all function designed to delete any that might have
    been leaked due to crashes (etc.).  The high-level algorithm is to:

    * Delete every database with a name like zulip_test_template_*
    * Unless it is registered in a file under TEMPLATE_DATABASE_DIR as
      part of a currently running test-backend invocation
    * And that file is less expiry_time old.

    This should ensure we ~never break a running test-backend process,
    while also ensuring we will eventually delete all leaked databases.
    """
    files = glob.glob(os.path.join(UUID_VAR_DIR, TEMPLATE_DATABASE_DIR, "*"))
    test_databases: set[str] = set()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT datname FROM pg_database;")
            rows = cursor.fetchall()
            for row in rows:
                if "zulip_test_template_" in row[0]:
                    test_databases.add(row[0])
    except ProgrammingError:
        pass

    databases_in_use: set[str] = set()
    for file in files:
        if round(time.time()) - os.path.getmtime(file) < expiry_time:
            with open(file) as f:
                databases_in_use.update(f"zulip_test_template_{line}".rstrip() for line in f)
        else:
            # Any test-backend run older than expiry_time can be
            # cleaned up, both the database and the file listing its
            # databases.
            os.remove(file)

    databases_to_drop = test_databases - databases_in_use

    if not databases_to_drop:
        return 0

    commands = "\n".join(f"DROP DATABASE IF EXISTS {db};" for db in databases_to_drop)
    subprocess.run(
        ["psql", "-q", "-v", "ON_ERROR_STOP=1", "-h", "localhost", "postgres", "zulip_test"],
        input=commands,
        check=True,
        text=True,
    )
    return len(databases_to_drop)


def remove_test_run_directories(expiry_time: int = 60 * 60) -> int:
    removed = 0
    directories = glob.glob(os.path.join(UUID_VAR_DIR, "test-backend", "run_*"))
    for test_run in directories:
        if round(time.time()) - os.path.getmtime(test_run) > expiry_time:
            try:
                shutil.rmtree(test_run)
                removed += 1
            except FileNotFoundError:
                pass
    return removed


def reset_zulip_test_database() -> None:
    """
    This function is used to reset the zulip_test database fastest way possible,
    i.e. First, it deletes the database and then clones it from zulip_test_template.
    This function is used with puppeteer tests, so it can quickly reset the test
    database after each run.
    """
    from zerver.lib.test_runner import destroy_test_databases

    # Make sure default database is 'zulip_test'.
    assert connections["default"].settings_dict["NAME"] == "zulip_test"

    # Clearing all the active PSQL sessions with 'zulip_test'.
    run(
        [
            "env",
            "PGHOST=localhost",
            "PGUSER=zulip_test",
            "scripts/setup/terminate-psql-sessions",
            "zulip_test",
        ]
    )

    destroy_test_databases()
    # Pointing default database to test database template, so we can instantly clone it.
    settings.DATABASES["default"]["NAME"] = BACKEND_DATABASE_TEMPLATE
    connection = connections["default"]
    clone_database_suffix = "clone"
    connection.creation.clone_test_db(
        suffix=clone_database_suffix,
    )
    settings_dict = connection.creation.get_test_db_clone_settings(clone_database_suffix)
    # We manually rename the clone database to 'zulip_test' because when cloning it,
    # its name is set to original database name + some suffix.
    # Also, we need it to be 'zulip_test' so that our running server can recognize it.
    with connection.cursor() as cursor:
        cursor.execute("ALTER DATABASE zulip_test_template_clone RENAME TO zulip_test;")
    settings_dict["NAME"] = "zulip_test"
    # connection.settings_dict must be updated in place for changes to be
    # reflected in django.db.connections. If the following line assigned
    # connection.settings_dict = settings_dict, new threads would connect
    # to the default database instead of the appropriate clone.
    connection.settings_dict.update(settings_dict)
    connection.close()
