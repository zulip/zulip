# -*- coding: utf-8 -*-
import json
import os
import re
import hashlib
import subprocess
import sys
from typing import Any, List, Optional
from importlib import import_module
from io import StringIO

from django.db import connections, DEFAULT_DB_ALIAS
from django.db.utils import OperationalError
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.utils.module_loading import module_has_submodule

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from scripts.lib.zulip_tools import get_dev_uuid_var_path, run

UUID_VAR_DIR = get_dev_uuid_var_path()
FILENAME_SPLITTER = re.compile(r'[\W\-_]')

def run_db_migrations(platform: str) -> None:
    if platform == 'dev':
        migration_status_file = 'migration_status_dev'
        settings = 'zproject.settings'
        db_name = 'ZULIP_DB_NAME=zulip'
    elif platform == 'test':
        migration_status_file = 'migration_status_test'
        settings = 'zproject.test_settings'
        db_name = 'ZULIP_DB_NAME=zulip_test_template'

    # We shell out to `manage.py` and pass `DJANGO_SETTINGS_MODULE` on
    # the command line rather than just calling the migration
    # functions, because Django doesn't support changing settings like
    # what the database is as runtime.
    # Also we export DB_NAME which is ignored by dev platform but
    # recognised by test platform and used to migrate correct db.
    run(['env', ('DJANGO_SETTINGS_MODULE=%s' % settings), db_name,
         './manage.py', 'migrate', '--no-input'])
    run(['env', ('DJANGO_SETTINGS_MODULE=%s' % settings), db_name,
         './manage.py', 'get_migration_status',
         '--output=%s' % (migration_status_file)])

def run_generate_fixtures_if_required(use_force: bool=False) -> None:
    generate_fixtures_command = ['tools/setup/generate-fixtures']
    test_template_db_status = template_database_status()
    if use_force or test_template_db_status == 'needs_rebuild':
        generate_fixtures_command.append('--force')
    elif test_template_db_status == 'run_migrations':
        run_db_migrations('test')
    subprocess.check_call(generate_fixtures_command)

def database_exists(database_name: str, **options: Any) -> bool:
    db = options.get('database', DEFAULT_DB_ALIAS)
    try:
        connection = connections[db]

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 from pg_database WHERE datname='{}';".format(database_name))
            return_value = bool(cursor.fetchone())
        connections.close_all()
        return return_value
    except OperationalError:
        return False

def get_migration_status(**options: Any) -> str:
    verbosity = options.get('verbosity', 1)

    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "management"):
            import_module('.management', app_config.name)

    app_label = options['app_label'] if options.get('app_label') else None
    db = options.get('database', DEFAULT_DB_ALIAS)
    out = StringIO()
    call_command(
        'showmigrations',
        '--list',
        app_label=app_label,
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
    return re.sub(r'\x1b\[(1|0)m', '', output)

def extract_migrations_as_list(migration_status: str) -> List[str]:
    MIGRATIONS_RE = re.compile(r'\[[X| ]\] (\d+_.+)\n')
    return MIGRATIONS_RE.findall(migration_status)

def what_to_do_with_migrations(migration_file: str, **options: Any) -> str:
    if not os.path.exists(migration_file):
        return 'scrap'

    with open(migration_file) as f:
        previous_migration_status = f.read()
    current_migration_status = get_migration_status(**options)
    all_curr_migrations = extract_migrations_as_list(current_migration_status)
    all_prev_migrations = extract_migrations_as_list(previous_migration_status)

    if len(all_curr_migrations) < len(all_prev_migrations):
        return 'scrap'

    for migration in all_prev_migrations:
        if migration not in all_curr_migrations:
            return 'scrap'

    if len(all_curr_migrations) == len(all_prev_migrations):
        return 'migrations_are_latest'

    return 'migrate'

def _get_hash_file_path(source_file_path: str, status_dir: str) -> str:
    basename = os.path.basename(source_file_path)
    filename = '_'.join(FILENAME_SPLITTER.split(basename)).lower()
    return os.path.join(status_dir, filename)

def _check_hash(source_hash_file: str, target_content: str) -> bool:
    """
    This function has a side effect of creating a new hash file or
    updating the old hash file.
    """
    target_hash_content = hashlib.sha1(target_content.encode('utf8')).hexdigest()

    if not os.path.exists(source_hash_file):
        source_hash_content = None
    else:
        with open(source_hash_file) as f:
            source_hash_content = f.read().strip()

    with open(source_hash_file, 'w') as f:
        f.write(target_hash_content)

    return source_hash_content == target_hash_content

def check_file_hash(target_file_path: str, status_dir: str) -> bool:
    source_hash_file = _get_hash_file_path(target_file_path, status_dir)

    with open(target_file_path) as f:
        target_content = f.read()

    return _check_hash(source_hash_file, target_content)

def check_setting_hash(setting_name: str, status_dir: str) -> bool:
    hash_filename = '_'.join(['settings', setting_name])
    source_hash_file = os.path.join(status_dir, hash_filename)

    target_content = json.dumps(getattr(settings, setting_name), sort_keys=True)

    return _check_hash(source_hash_file, target_content)

def template_database_status(
        database_name: str='zulip_test_template',
        migration_status: Optional[str]=None,
        settings: str='zproject.test_settings',
        status_dir: Optional[str]=None,
        check_files: Optional[List[str]]=None,
        check_settings: Optional[List[str]]=None) -> str:
    # This function returns a status string specifying the type of
    # state the template db is in and thus the kind of action required.
    if check_files is None:
        check_files = [
            'zilencer/management/commands/populate_db.py',
            'zerver/lib/bulk_create.py',
            'zerver/lib/generate_test_data.py',
            'tools/setup/postgres-init-test-db',
            'tools/setup/postgres-init-dev-db',
        ]
    if check_settings is None:
        check_settings = [
            'REALM_INTERNAL_BOTS',
        ]
    if status_dir is None:
        status_dir = os.path.join(UUID_VAR_DIR, 'test_db_status')
    if migration_status is None:
        migration_status = os.path.join(UUID_VAR_DIR, 'migration_status_test')

    if not os.path.exists(status_dir):
        os.mkdir(status_dir)

    if database_exists(database_name):
        # To ensure Python evaluates all the hash tests (and thus creates the
        # hash files about the current state), we evaluate them in a
        # list and then process the result
        files_hash_status = all([check_file_hash(fn, status_dir) for fn in check_files])
        settings_hash_status = all([check_setting_hash(setting_name, status_dir)
                                    for setting_name in check_settings])
        hash_status = files_hash_status and settings_hash_status
        if not hash_status:
            return 'needs_rebuild'

        migration_op = what_to_do_with_migrations(migration_status, settings=settings)
        if migration_op == 'scrap':
            return 'needs_rebuild'

        if migration_op == 'migrate':
            return 'run_migrations'

        return 'current'

    return 'needs_rebuild'
