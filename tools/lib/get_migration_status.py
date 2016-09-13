# -*- coding: utf-8 -*-
import os
import re
from typing import Any
from six import text_type
from importlib import import_module
from six.moves import cStringIO as StringIO

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections
from django.core.management import call_command
from django.utils.module_loading import module_has_submodule


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
