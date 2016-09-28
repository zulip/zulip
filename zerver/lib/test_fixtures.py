# -*- coding: utf-8 -*-
import os
import re
import filecmp
from typing import Any
from importlib import import_module
from six import text_type
from six.moves import cStringIO as StringIO

from django.db import connections, DEFAULT_DB_ALIAS
from django.apps import apps
from django.core.management import call_command
from django.utils.module_loading import module_has_submodule

def compare_files_if_exist(file1, file2):
    # type: (text_type, text_type) -> bool
    return os.path.exists(file1) and os.path.exists(file2) and filecmp.cmp(file1, file2)

def check_if_database_exist(database_name, **options):
    # type: (text_type, **Any) -> bool
    db = options.get('database', DEFAULT_DB_ALIAS)
    connection = connections[db]

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 from pg_database WHERE datname='{}';".format(database_name))
        return_value = bool(cursor.fetchone())
    connections.close_all()
    return return_value

def get_migration_status(**options):
    # type: (**Any) -> str
    verbosity = options.get('verbosity', 1)

    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "management"):
            import_module('.management', app_config.name)

    app_labels = [options['app_label']] if options.get('app_label') else None
    db = options.get('database', DEFAULT_DB_ALIAS)
    out = StringIO()
    call_command(
        'showmigrations',
        '--list',
        app_labels=app_labels,
        database=db,
        no_color=options.get('no_color', False),
        settings=options.get('settings', os.environ['DJANGO_SETTINGS_MODULE']),
        stdout=out,
        traceback=options.get('traceback', True),
        verbosity=verbosity,
    )
    connections.close_all()
    out.seek(0)
    output = out.read()
    return re.sub('\x1b\[(1|0)m', '', output)
