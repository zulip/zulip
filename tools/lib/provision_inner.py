#!/usr/bin/env python3
import os
import sys
import argparse
import glob
import shutil

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.append(ZULIP_PATH)
from scripts.lib.zulip_tools import run, run_as_root, OKBLUE, ENDC, \
    get_dev_uuid_var_path, file_or_package_hash_updated

from version import PROVISION_VERSION

from tools.setup.generate_zulip_bots_static_files import generate_zulip_bots_static_files

VENV_PATH = "/srv/zulip-py3-venv"
VAR_DIR_PATH = os.path.join(ZULIP_PATH, 'var')
LOG_DIR_PATH = os.path.join(VAR_DIR_PATH, 'log')
UPLOAD_DIR_PATH = os.path.join(VAR_DIR_PATH, 'uploads')
TEST_UPLOAD_DIR_PATH = os.path.join(VAR_DIR_PATH, 'test_uploads')
COVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'coverage')
NODE_TEST_COVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'node-coverage')
XUNIT_XML_TEST_RESULTS_DIR_PATH = os.path.join(VAR_DIR_PATH, 'xunit-test-results')

is_travis = 'TRAVIS' in os.environ

# TODO: De-duplicate this with emoji_dump.py
EMOJI_CACHE_PATH = "/srv/zulip-emoji-cache"
if is_travis:
    # In Travis CI, we don't have root access
    EMOJI_CACHE_PATH = "/home/travis/zulip-emoji-cache"

UUID_VAR_PATH = get_dev_uuid_var_path()

def setup_shell_profile(shell_profile):
    # type: (str) -> None
    shell_profile_path = os.path.expanduser(shell_profile)

    def write_command(command):
        # type: (str) -> None
        if os.path.exists(shell_profile_path):
            with open(shell_profile_path) as shell_profile_file:
                lines = [line.strip() for line in shell_profile_file.readlines()]
            if command not in lines:
                with open(shell_profile_path, 'a+') as shell_profile_file:
                    shell_profile_file.writelines(command + '\n')
        else:
            with open(shell_profile_path, 'w') as shell_profile_file:
                shell_profile_file.writelines(command + '\n')

    source_activate_command = "source " + os.path.join(VENV_PATH, "bin", "activate")
    write_command(source_activate_command)
    if os.path.exists('/srv/zulip'):
        write_command('cd /srv/zulip')

def setup_bash_profile() -> None:
    """Select a bash profile file to add setup code to."""

    BASH_PROFILES = [
        os.path.expanduser(p) for p in
        ("~/.bash_profile", "~/.bash_login", "~/.profile")
    ]

    def clear_old_profile() -> None:
        # An earlier version of this script would output a fresh .bash_profile
        # even though a .profile existed in the image used. As a convenience to
        # existing developers (and, perhaps, future developers git-bisecting the
        # provisioning scripts), check for this situation, and blow away the
        # created .bash_profile if one is found.

        BASH_PROFILE = BASH_PROFILES[0]
        DOT_PROFILE = BASH_PROFILES[2]
        OLD_PROFILE_TEXT = "source /srv/zulip-py3-venv/bin/activate\n" + \
            "cd /srv/zulip\n"

        if os.path.exists(DOT_PROFILE):
            try:
                with open(BASH_PROFILE) as f:
                    profile_contents = f.read()
                if profile_contents == OLD_PROFILE_TEXT:
                    os.unlink(BASH_PROFILE)
            except FileNotFoundError:
                pass

    clear_old_profile()

    for candidate_profile in BASH_PROFILES:
        if os.path.exists(candidate_profile):
            setup_shell_profile(candidate_profile)
            break
    else:
        # no existing bash profile found; claim .bash_profile
        setup_shell_profile(BASH_PROFILES[0])

def main(options: argparse.Namespace) -> int:
    setup_bash_profile()
    setup_shell_profile('~/.zprofile')

    # This needs to happen before anything that imports zproject.settings.
    run(["scripts/setup/generate_secrets.py", "--development"])

    # create log directory `zulip/var/log`
    os.makedirs(LOG_DIR_PATH, exist_ok=True)
    # create upload directory `var/uploads`
    os.makedirs(UPLOAD_DIR_PATH, exist_ok=True)
    # create test upload directory `var/test_upload`
    os.makedirs(TEST_UPLOAD_DIR_PATH, exist_ok=True)
    # create coverage directory `var/coverage`
    os.makedirs(COVERAGE_DIR_PATH, exist_ok=True)
    # create linecoverage directory `var/node-coverage`
    os.makedirs(NODE_TEST_COVERAGE_DIR_PATH, exist_ok=True)
    # create XUnit XML test results directory`var/xunit-test-results`
    os.makedirs(XUNIT_XML_TEST_RESULTS_DIR_PATH, exist_ok=True)

    # The `build_emoji` script requires `emoji-datasource` package
    # which we install via npm; thus this step is after installing npm
    # packages.
    if not os.access(EMOJI_CACHE_PATH, os.W_OK):
        run_as_root(["mkdir", "-p", EMOJI_CACHE_PATH])
        run_as_root(["chown", "%s:%s" % (os.getuid(), os.getgid()), EMOJI_CACHE_PATH])
    run(["tools/setup/emoji/build_emoji"])

    # copy over static files from the zulip_bots package
    generate_zulip_bots_static_files()

    build_pygments_data_paths = ["tools/setup/build_pygments_data", "tools/setup/lang.json"]
    from pygments import __version__ as pygments_version
    if not os.path.exists("static/generated/pygments_data.json") or file_or_package_hash_updated(
            build_pygments_data_paths, "build_pygments_data_hash", options.is_force,
            [pygments_version]):
        run(["tools/setup/build_pygments_data"])
    else:
        print("No need to run `tools/setup/build_pygments_data`.")

    email_source_paths = ["scripts/setup/inline_email_css.py", "templates/zerver/emails/email.css"]
    email_source_paths += glob.glob('templates/zerver/emails/*.source.html')
    if file_or_package_hash_updated(email_source_paths, "last_email_source_files_hash", options.is_force):
        run(["scripts/setup/inline_email_css.py"])
    else:
        print("No need to run `scripts/setup/inline_email_css.py`.")

    if not options.is_production_travis:
        # The following block is skipped for the production Travis
        # suite, because that suite doesn't make use of these elements
        # of the development environment (it just uses the development
        # environment to build a release tarball).

        # Need to set up Django before using template_database_status
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
        import django
        django.setup()

        from zerver.lib.test_fixtures import template_database_status, run_db_migrations, \
            destroy_leaked_test_databases

        try:
            from zerver.lib.queue import SimpleQueueClient
            SimpleQueueClient()
            rabbitmq_is_configured = True
        except Exception:
            rabbitmq_is_configured = False

        if options.is_force or not rabbitmq_is_configured:
            run(["scripts/setup/configure-rabbitmq"])
        else:
            print("RabbitMQ is already configured.")

        dev_template_db_status = template_database_status('dev')
        if options.is_force or dev_template_db_status == 'needs_rebuild':
            run(["tools/setup/postgres-init-dev-db"])
            run(["tools/do-destroy-rebuild-database"])
        elif dev_template_db_status == 'run_migrations':
            run_db_migrations('dev')
        elif dev_template_db_status == 'current':
            print("No need to regenerate the dev DB.")

        test_template_db_status = template_database_status('test')
        if options.is_force or test_template_db_status == 'needs_rebuild':
            run(["tools/setup/postgres-init-test-db"])
            run(["tools/do-destroy-rebuild-test-database"])
        elif test_template_db_status == 'run_migrations':
            run_db_migrations('test')
        elif test_template_db_status == 'current':
            print("No need to regenerate the test DB.")

        # Consider updating generated translations data: both `.mo`
        # files and `language-options.json`.
        paths = ['zerver/management/commands/compilemessages.py']
        paths += glob.glob('locale/*/LC_MESSAGES/*.po')
        paths += glob.glob('locale/*/translations.json')

        if file_or_package_hash_updated(paths, "last_compilemessages_hash", options.is_force):
            run(["./manage.py", "compilemessages"])
        else:
            print("No need to run `manage.py compilemessages`.")

        destroyed = destroy_leaked_test_databases()
        if destroyed:
            print("Dropped %s stale test databases!" % (destroyed,))

    run(["scripts/lib/clean-unused-caches", "--threshold=6"])

    # Keeping this cache file around can cause eslint to throw
    # random TypeErrors when new/updated dependencies are added
    if os.path.isfile('.eslintcache'):
        # Remove this block when
        # https://github.com/eslint/eslint/issues/11639 is fixed
        # upstream.
        os.remove('.eslintcache')

    # Clean up the root of the `var/` directory for various
    # testing-related files that we have migrated to
    # `var/<uuid>/test-backend`.
    print("Cleaning var/ directory files...")
    var_paths = glob.glob('var/test*')
    var_paths.append('var/bot_avatar')
    for path in var_paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except FileNotFoundError:
            pass

    version_file = os.path.join(UUID_VAR_PATH, 'provision_version')
    print('writing to %s\n' % (version_file,))
    open(version_file, 'w').write(PROVISION_VERSION + '\n')

    print()
    print(OKBLUE + "Zulip development environment setup succeeded!" + ENDC)
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', dest='is_force',
                        default=False,
                        help="Ignore all provisioning optimizations.")

    parser.add_argument('--production-travis', action='store_true',
                        dest='is_production_travis',
                        default=False,
                        help="Provision for Travis with production settings.")

    options = parser.parse_args()
    sys.exit(main(options))
