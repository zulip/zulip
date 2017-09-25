#!/usr/bin/env python3
from __future__ import print_function
import os
import sys
import logging
import argparse
import platform
import subprocess
import glob
import hashlib

os.environ["PYTHONUNBUFFERED"] = "y"

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.append(ZULIP_PATH)
from scripts.lib.zulip_tools import run, subprocess_text_output, OKBLUE, ENDC, WARNING
from scripts.lib.setup_venv import setup_virtualenv, VENV_DEPENDENCIES
from scripts.lib.node_cache import setup_node_modules, NODE_MODULES_CACHE_PATH

from version import PROVISION_VERSION
if False:
    from typing import Any


SUPPORTED_PLATFORMS = {
    "Ubuntu": [
        "trusty",
        "xenial",
        # Platforms that are blocked on on tsearch_extras
        # "stretch",
        # "zesty",
    ],
}

VENV_PATH = "/srv/zulip-py3-venv"
VAR_DIR_PATH = os.path.join(ZULIP_PATH, 'var')
LOG_DIR_PATH = os.path.join(VAR_DIR_PATH, 'log')
UPLOAD_DIR_PATH = os.path.join(VAR_DIR_PATH, 'uploads')
TEST_UPLOAD_DIR_PATH = os.path.join(VAR_DIR_PATH, 'test_uploads')
COVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'coverage')
LINECOVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'linecoverage-report')
NODE_TEST_COVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'node-coverage')

# TODO: De-duplicate this with emoji_dump.py
EMOJI_CACHE_PATH = "/srv/zulip-emoji-cache"
if 'TRAVIS' in os.environ:
    # In Travis CI, we don't have root access
    EMOJI_CACHE_PATH = "/home/travis/zulip-emoji-cache"

if not os.path.exists(os.path.join(ZULIP_PATH, ".git")):
    print("Error: No Zulip git repository present!")
    print("To setup the Zulip development environment, you should clone the code")
    print("from GitHub, rather than using a Zulip production release tarball.")
    sys.exit(1)

# Check the RAM on the user's system, and throw an effort if <1.5GB.
# This avoids users getting segfaults running `pip install` that are
# generally more annoying to debug.
with open("/proc/meminfo") as meminfo:
    ram_size = meminfo.readlines()[0].strip().split(" ")[-2]
ram_gb = float(ram_size) / 1024.0 / 1024.0
if ram_gb < 1.5:
    print("You have insufficient RAM (%s GB) to run the Zulip development environment." % (
        round(ram_gb, 2),))
    print("We recommend at least 2 GB of RAM, and require at least 1.5 GB.")
    sys.exit(1)

try:
    run(["mkdir", "-p", VAR_DIR_PATH])
    if os.path.exists(os.path.join(VAR_DIR_PATH, 'zulip-test-symlink')):
        os.remove(os.path.join(VAR_DIR_PATH, 'zulip-test-symlink'))
    os.symlink(
        os.path.join(ZULIP_PATH, 'README.md'),
        os.path.join(VAR_DIR_PATH, 'zulip-test-symlink')
    )
    os.remove(os.path.join(VAR_DIR_PATH, 'zulip-test-symlink'))
except OSError as err:
    print("Error: Unable to create symlinks. Make sure you have permission to create symbolic links.")
    print("See this page for more information:")
    print("  http://zulip.readthedocs.io/en/latest/dev-env-first-time-contributors.html#os-symlink-error")
    sys.exit(1)

if platform.architecture()[0] == '64bit':
    arch = 'amd64'
elif platform.architecture()[0] == '32bit':
    arch = "i386"
else:
    logging.critical("Only x86 is supported; ping zulip-devel@googlegroups.com if you want another architecture.")
    sys.exit(1)

# Ideally we wouldn't need to install a dependency here, before we
# know the codename.
subprocess.check_call(["sudo", "apt-get", "install", "-y", "lsb-release"])
vendor = subprocess_text_output(["lsb_release", "-is"])
codename = subprocess_text_output(["lsb_release", "-cs"])
if not (vendor in SUPPORTED_PLATFORMS and codename in SUPPORTED_PLATFORMS[vendor]):
    logging.critical("Unsupported platform: {} {}".format(vendor, codename))
    sys.exit(1)

POSTGRES_VERSION_MAP = {
    "stretch": "9.6",
    "trusty": "9.3",
    "xenial": "9.5",
    "zesty": "9.6",
}
POSTGRES_VERSION = POSTGRES_VERSION_MAP[codename]

UBUNTU_COMMON_APT_DEPENDENCIES = [
    "closure-compiler",
    "memcached",
    "rabbitmq-server",
    "redis-server",
    "hunspell-en-us",
    "supervisor",
    "git",
    "libssl-dev",
    "yui-compressor",
    "wget",
    "ca-certificates",      # Explicit dependency in case e.g. wget is already installed
    "puppet",               # Used by lint
    "gettext",              # Used by makemessages i18n
    "curl",                 # Used for fetching PhantomJS as wget occasionally fails on redirects
    "netcat",               # Used for flushing memcached
    "moreutils",            # Used for sponge command
] + VENV_DEPENDENCIES

APT_DEPENDENCIES = {
    "stretch": UBUNTU_COMMON_APT_DEPENDENCIES + [
        "postgresql-9.6",
        # tsearch-extras removed because there's no apt repository hosting it for Debian.
        # "postgresql-9.6-tsearch-extras",
        "postgresql-9.6-pgroonga",
        # Technically, this should be in VENV_DEPENDENCIES, but it
        # doesn't exist in trusty and we don't have a conditional on
        # platform there.
        "virtualenv",
    ],
    "trusty": UBUNTU_COMMON_APT_DEPENDENCIES + [
        "postgresql-9.3",
        "postgresql-9.3-tsearch-extras",
        "postgresql-9.3-pgroonga",
    ],
    "xenial": UBUNTU_COMMON_APT_DEPENDENCIES + [
        "postgresql-9.5",
        "postgresql-9.5-tsearch-extras",
        "postgresql-9.5-pgroonga",
    ],
    "zesty": UBUNTU_COMMON_APT_DEPENDENCIES + [
        "postgresql-9.6",
        "postgresql-9.6-pgroonga",
        "virtualenv",
    ],
}

TSEARCH_STOPWORDS_PATH = "/usr/share/postgresql/%s/tsearch_data/" % (POSTGRES_VERSION,)
REPO_STOPWORDS_PATH = os.path.join(
    ZULIP_PATH,
    "puppet",
    "zulip",
    "files",
    "postgresql",
    "zulip_english.stop",
)

LOUD = dict(_out=sys.stdout, _err=sys.stderr)

user_id = os.getuid()

def setup_shell_profile(shell_profile):
    # type: (str) -> None
    shell_profile_path = os.path.expanduser(shell_profile)

    def write_command(command):
        # type: (str) -> None
        if os.path.exists(shell_profile_path):
            with open(shell_profile_path, 'a+') as shell_profile_file:
                if command not in shell_profile_file.read():
                    shell_profile_file.writelines(command + '\n')
        else:
            with open(shell_profile_path, 'w') as shell_profile_file:
                shell_profile_file.writelines(command + '\n')

    source_activate_command = "source " + os.path.join(VENV_PATH, "bin", "activate")
    write_command(source_activate_command)
    write_command('cd /srv/zulip')

def install_apt_deps():
    # type: () -> None
    # setup-apt-repo does an `apt-get update`
    run(["sudo", "./scripts/lib/setup-apt-repo"])
    run(["sudo", "apt-get", "-y", "install", "--no-install-recommends"] + APT_DEPENDENCIES[codename])

def main(options):
    # type: (Any) -> int

    # yarn and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    # setup-apt-repo does an `apt-get update`
    # hash the apt dependencies
    sha_sum = hashlib.sha1()

    for apt_depedency in APT_DEPENDENCIES[codename]:
        sha_sum.update(apt_depedency.encode('utf8'))
    # hash the content of setup-apt-repo
    sha_sum.update(open('scripts/lib/setup-apt-repo').read().encode('utf8'))

    new_apt_dependencies_hash = sha_sum.hexdigest()
    last_apt_dependencies_hash = None
    apt_hash_file_path = 'var/apt_dependencies_hash'
    try:
        hash_file = open(apt_hash_file_path, 'r+')
        last_apt_dependencies_hash = hash_file.read()
    except IOError:
        run(['touch', apt_hash_file_path])
        hash_file = open(apt_hash_file_path, 'r+')

    if (new_apt_dependencies_hash != last_apt_dependencies_hash):
        try:
            install_apt_deps()
        except subprocess.CalledProcessError:
            # Might be a failure due to network connection issues. Retrying...
            print(WARNING + "`apt-get -y install` failed while installing dependencies; retrying..." + ENDC)
            install_apt_deps()
        hash_file.write(new_apt_dependencies_hash)
    else:
        print("No changes to apt dependencies, so skipping apt operations.")

    # Here we install node.
    run(["sudo", "scripts/lib/install-node"])

    # This is a wrapper around `yarn`, which we run last since
    # it can often fail due to network issues beyond our control.
    try:
        # Hack: We remove `node_modules` as root to work around an
        # issue with the symlinks being improperly owned by root.
        if os.path.islink("node_modules"):
            run(["sudo", "rm", "-f", "node_modules"])
        if not os.path.isdir(NODE_MODULES_CACHE_PATH):
            run(["sudo", "mkdir", NODE_MODULES_CACHE_PATH])
        run(["sudo", "chown", "%s:%s" % (user_id, user_id), NODE_MODULES_CACHE_PATH])
        setup_node_modules(prefer_offline=True)
    except subprocess.CalledProcessError:
        print(WARNING + "`yarn install` failed; retrying..." + ENDC)
        setup_node_modules()

    # Import tools/setup_venv.py instead of running it so that we get an
    # activated virtualenv for the rest of the provisioning process.
    from tools.setup import setup_venvs
    setup_venvs.main(options.is_travis)

    setup_shell_profile('~/.bash_profile')
    setup_shell_profile('~/.zprofile')

    run(["sudo", "cp", REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH])

    # create log directory `zulip/var/log`
    run(["mkdir", "-p", LOG_DIR_PATH])
    # create upload directory `var/uploads`
    run(["mkdir", "-p", UPLOAD_DIR_PATH])
    # create test upload directory `var/test_upload`
    run(["mkdir", "-p", TEST_UPLOAD_DIR_PATH])
    # create coverage directory`var/coverage`
    run(["mkdir", "-p", COVERAGE_DIR_PATH])
    # create linecoverage directory`var/linecoverage-report`
    run(["mkdir", "-p", LINECOVERAGE_DIR_PATH])
    # create linecoverage directory`var/node-coverage`
    run(["mkdir", "-p", NODE_TEST_COVERAGE_DIR_PATH])

    # `build_emoji` script requires `emoji-datasource` package which we install
    # via npm and hence it should be executed after we are done installing npm
    # packages.
    if not os.path.isdir(EMOJI_CACHE_PATH):
        run(["sudo", "mkdir", EMOJI_CACHE_PATH])
    run(["sudo", "chown", "%s:%s" % (user_id, user_id), EMOJI_CACHE_PATH])
    run(["tools/setup/emoji/build_emoji"])

    # copy over static files from the zulip_bots package
    run(["tools/setup/generate_zulip_bots_static_files"])

    run(["tools/setup/build_pygments_data.py"])
    run(["scripts/setup/generate_secrets.py", "--development"])
    run(["tools/update-authors-json", "--use-fixture"])
    run(["tools/inline-email-css"])
    if options.is_travis and not options.is_production_travis:
        run(["sudo", "service", "rabbitmq-server", "restart"])
        run(["sudo", "service", "redis-server", "restart"])
        run(["sudo", "service", "memcached", "restart"])
    elif options.is_docker:
        run(["sudo", "service", "rabbitmq-server", "restart"])
        run(["sudo", "pg_dropcluster", "--stop", POSTGRES_VERSION, "main"])
        run(["sudo", "pg_createcluster", "-e", "utf8", "--start", POSTGRES_VERSION, "main"])
        run(["sudo", "service", "redis-server", "restart"])
        run(["sudo", "service", "memcached", "restart"])
    if not options.is_production_travis:
        # The following block is skipped for the production Travis
        # suite, because that suite doesn't make use of these elements
        # of the development environment (it just uses the development
        # environment to build a release tarball).

        # Need to set up Django before using is_template_database_current
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
        import django
        django.setup()

        from zerver.lib.str_utils import force_bytes
        from zerver.lib.test_fixtures import is_template_database_current

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

        if options.is_force or not is_template_database_current(
                migration_status="var/migration_status_dev",
                settings="zproject.settings",
                database_name="zulip",
        ):
            run(["tools/setup/postgres-init-dev-db"])
            run(["tools/do-destroy-rebuild-database"])
        else:
            print("No need to regenerate the dev DB.")

        if options.is_force or not is_template_database_current():
            run(["tools/setup/postgres-init-test-db"])
            run(["tools/do-destroy-rebuild-test-database"])
        else:
            print("No need to regenerate the test DB.")

        # Consider updating generated translations data: both `.mo`
        # files and `language-options.json`.
        sha1sum = hashlib.sha1()
        paths = ['zerver/management/commands/compilemessages.py']
        paths += glob.glob('static/locale/*/LC_MESSAGES/*.po')
        paths += glob.glob('static/locale/*/translations.json')

        for path in paths:
            with open(path, 'r') as file_to_hash:
                sha1sum.update(force_bytes(file_to_hash.read()))

        new_compilemessages_hash = sha1sum.hexdigest()
        run(['touch', 'var/last_compilemessages_hash'])
        with open('var/last_compilemessages_hash', 'r') as hash_file:
            last_compilemessages_hash = hash_file.read()

        if options.is_force or (new_compilemessages_hash != last_compilemessages_hash):
            with open('var/last_compilemessages_hash', 'w') as hash_file:
                hash_file.write(new_compilemessages_hash)
            run(["./manage.py", "compilemessages"])
        else:
            print("No need to run `manage.py compilemessages`.")

    version_file = os.path.join(ZULIP_PATH, 'var/provision_version')
    print('writing to %s\n' % (version_file,))
    open(version_file, 'w').write(PROVISION_VERSION + '\n')

    print()
    print(OKBLUE + "Zulip development environment setup succeeded!" + ENDC)
    return 0

if __name__ == "__main__":
    description = ("Provision script to install Zulip")
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--force', action='store_true', dest='is_force',
                        default=False,
                        help="Ignore all provisioning optimizations.")

    parser.add_argument('--travis', action='store_true', dest='is_travis',
                        default=False,
                        help="Provision for Travis but without production settings.")

    parser.add_argument('--production-travis', action='store_true',
                        dest='is_production_travis',
                        default=False,
                        help="Provision for Travis but with production settings.")

    parser.add_argument('--docker', action='store_true',
                        dest='is_docker',
                        default=False,
                        help="Provision for Docker.")

    options = parser.parse_args()
    sys.exit(main(options))
