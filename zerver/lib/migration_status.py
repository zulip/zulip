import os
import re
from importlib import import_module
from io import StringIO
from typing import Any, TypeAlias, TypedDict

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
    migration_status_print: str, stale_migrations: list[tuple[str, str]] = STALE_MIGRATIONS
) -> AppMigrations:
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
