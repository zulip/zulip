import os
import re
from importlib import import_module
from io import StringIO
from typing import Any


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
    return re.sub(r"\x1b\[(1|0)m", "", output)
