import os
import re
from importlib import import_module
from io import StringIO
from typing import Any, TypeAlias, TypedDict

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

AppMigrations: TypeAlias = dict[str, list[str]]


class MigrationStatusJson(TypedDict):
    migrations_by_app: AppMigrations
    zulip_version: str


STALE_MIGRATIONS = [
    # Ignore django-guardian, which we installed until 1.7.0~3134
    ("guardian", "0001_initial"),
    # Ignore django.contrib.sites, which we installed until 2.0.0-rc1~984.
    ("sites", "0001_initial"),
    ("sites", "0002_alter_domain_unique"),
    # These migrations (0002=>0028) were squashed into 0001, in 6fbddf578a6e
    # through a21f2d771553, 1.7.0~3135.
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
    # This migration was in python-social-auth, and was mistakenly removed
    # from its `replaces` in
    # https://github.com/python-social-auth/social-app-django/pull/25
    ("default", "0005_auto_20160727_2333"),
    # This was a typo (twofactor for two_factor) corrected in
    # https://github.com/jazzband/django-two-factor-auth/pull/642
    ("twofactor", "0001_squashed_0008_delete_phonedevice"),
]


def get_migration_status(**options: Any) -> str:
    from django.apps import apps
    from django.core.management import call_command
    from django.db import DEFAULT_DB_ALIAS
    from django.utils.module_loading import module_has_submodule

    verbosity = options.get("verbosity", 1)

    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "management"):
            import_module(".management", app_config.name)

    app_label = options["app_label"] if options.get("app_label") else None
    db = options.get("database", DEFAULT_DB_ALIAS)
    out = StringIO()
    command_args = ["--list"]
    if app_label:
        command_args.append(app_label)

    call_command(
        "showmigrations",
        *command_args,
        database=db,
        no_color=options.get("no_color", False),
        settings=options.get("settings", os.environ["DJANGO_SETTINGS_MODULE"]),
        stdout=out,
        skip_checks=options.get("skip_checks", True),
        traceback=options.get("traceback", True),
        verbosity=verbosity,
    )
    out.seek(0)
    output = out.read()
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def parse_migration_status(
    stale_migrations: list[tuple[str, str]] = STALE_MIGRATIONS,
) -> AppMigrations:
    """
    This is a copy of Django's `showmigrations` command, keep this in sync with
    the actual logic from Django. The key differences are, this returns a dict
    and filters out any migration found in the `stale_migrations` parameter.

    Django's `showmigrations`:
    https://github.com/django/django/blob/main/django/core/management/commands/showmigrations.py
    """
    # Load migrations from disk/DB
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    recorder = MigrationRecorder(connection)
    recorded_migrations = recorder.applied_migrations()
    graph = loader.graph
    migrations_dict: AppMigrations = {}
    app_names = sorted(loader.migrated_apps)
    stale_migrations_dict: dict[str, list[str]] = {}

    for app, migration in stale_migrations:
        if app not in stale_migrations_dict:
            stale_migrations_dict[app] = []
        stale_migrations_dict[app].append(migration)

    # For each app, print its migrations in order from oldest (roots) to
    # newest (leaves).
    for app_name in app_names:
        migrations_dict[app_name] = []
        shown = set()
        apps_stale_migrations = stale_migrations_dict.get(app_name, [])
        for node in graph.leaf_nodes(app_name):
            for plan_node in graph.forwards_plan(node):
                if (
                    plan_node not in shown
                    and plan_node[0] == app_name
                    and plan_node[1] not in apps_stale_migrations
                ):
                    # Give it a nice title if it's a squashed one
                    title = plan_node[1]

                    if graph.nodes[plan_node].replaces:
                        title += f" ({len(graph.nodes[plan_node].replaces)} squashed migrations)"

                    applied_migration = loader.applied_migrations.get(plan_node)
                    # Mark it as applied/unapplied
                    if applied_migration:
                        if plan_node in recorded_migrations:
                            output = f"[X] {title}"
                        else:
                            output = f"[-] {title}"
                    else:
                        output = f"[ ] {title}"
                    migrations_dict[app_name].append(output)
                    shown.add(plan_node)
        # If there are no migrations, record as such
        if not shown:
            output = "(no migrations)"
            migrations_dict[app_name].append(output)
    return migrations_dict
