#!/usr/bin/env python3
import os
import sys
import logging
import argparse
import platform
import hashlib
from subprocess import CalledProcessError
from glob import glob
from pathlib import Path
from contextlib import contextmanager

class DummyType(object):
    def __getitem__(self, key):  # type: ignore # 3.4
        return self

try:
    from typing import Any, Tuple, Iterator
except ImportError:
    Any = DummyType()  # type: ignore # 3.4
    Tuple = DummyType()  # type: ignore # 3.4
    Iterator = DummyType()  # type: ignore # 3.4

_zulip_path = str(Path(__file__).absolute().parent.parent.parent)
sys.path.append(_zulip_path)
from scripts.lib.zulip_tools import (
    run, subprocess_text_output, OKBLUE, ENDC, WARNING,
    get_dev_uuid_var_path, FAIL
)
from scripts.lib import setup_venv
from scripts.lib.node_cache import setup_node_modules, NODE_MODULES_CACHE_PATH
import version


is_travis = 'TRAVIS' in os.environ
is_circleci = 'CIRCLECI' in os.environ
os.environ["PYTHONUNBUFFERED"] = "y"


SUPPORTED_PLATFORMS = {
    "Ubuntu": [
        "trusty",
        "xenial",
        # Platforms that are blocked on on tsearch_extras
        # "stretch",
        # "zesty",
    ],
}


def _travis_codename():
    with open('/etc/lsb-release') as f:
        generator = (l.split('=') for l in f)
        for (k, v) in generator:
            if k.strip() == 'DISTRIB_CODENAME':
                return v.strip()

def _codename():
    if is_travis:
        return _travis_codename.__func__()
    dist, version, codename = platform.linux_distribution()
    if codename not in SUPPORTED_PLATFORMS.get(dist, ()):
        logging.critical("Unsupported distro: %r" % ((dist, version, CODENAME),))
        raise RuntimeError()
    return codename

class Versions:
    PROVISION = version.PROVISION_VERSION
    POSTGRES_MAP = {
        'stretch': '9.6',
        'trusty': '9.3',
        'xenial': '9.5',
        'zesty': '9.6',
    }
    CODENAME = _codename()
    POSTGRES = POSTGRES_MAP[CODENAME]


class Paths:
    ZULIP = _zulip_path
    NODE_MODULES_CACHE = NODE_MODULES_CACHE_PATH

    VENV = '/srv/zulip-py3-venv'
    EMOJI_CACHE = '/srv/zulip-emoji-cache'

    VAR = ZULIP + '/var'
    LOG = VAR + '/log'
    UPLOAD = VAR + '/uploads'
    TEST_UPLOAD = VAR + '/test_uploads'
    COVERAGE = VAR + '/coverage'
    LINECOVERAGE = VAR + '/linecoverage-report'
    NODE_COVERAGE = VAR + '/node_coverage'

    TSEARCH_STOPWORDS = '/usr/share/postgresql/' + Versions.POSTGRES + '/tsearch_data/'
    REPO_STOPWORDS = ZULIP + '/puppet/zulip/files/postgresql/zulip_english.stop'

    # TODO: De-duplicate this with emoji_dump.py
    # TODO: How to deploy emoji without root?
    if is_travis:
        # In Travis CI, we don't have root access
        EMOJI_CACHE = os.path.expanduser('~') + '/zulip-emoji-cache'


class Deps:
    VENV = setup_venv.VENV_DEPENDENCIES
    THUMBOR_VENV = setup_venv.THUMBOR_VENV_DEPENDENCIES

    _UBUNTU_COMMON = [
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
    ]
    UBUNTU_COMMON = _UBUNTU_COMMON + VENV + THUMBOR_VENV

    _APT_MAP = {
        'stretch': [
            "postgresql-9.6",
            # tsearch-extras removed because there's no apt repository hosting it for Debian.
            # "postgresql-9.6-tsearch-extras",
            "postgresql-9.6-pgroonga",
            # Technically, this should be in VENV_DEPENDENCIES, but it
            # doesn't exist in trusty and we don't have a conditional on
            # platform there.
            "virtualenv",
        ],
        'trusty': [
            "postgresql-9.3",
            "postgresql-9.3-tsearch-extras",
            "postgresql-9.3-pgroonga",
        ],
        'xenial': [
            "postgresql-9.5",
            "postgresql-9.5-tsearch-extras",
            "postgresql-9.5-pgroonga",
            "virtualenv",  # see comment on stretch
        ],
        'zesty': [
            "postgresql-9.6",
            "postgresql-9.6-pgroonga",
            "virtualenv",  # see comment on stretch
        ],
    }
    APT = _APT_MAP[Versions.CODENAME] + UBUNTU_COMMON


def ram_size_gb() -> float:
    with open("/proc/meminfo") as meminfo:
        ram_size = meminfo.readlines()[0].strip().split(" ")[-2]
    return float(ram_size) / 1024.0 / 1024.0

def check_platform() -> None:
    bits, linkage = platform.architecture()
    if bits not in ('64bit', '32bit'):
        logging.critical("Only x86/64 is supported; ping "
                         "zulip-devel@googlegroups.com if you want "
                         "a " + bits + " version.")
        raise RuntimeError()

@contextmanager
def removing(path: str) -> Iterator[None]:
    if os.path.exists(path):
        os.remove(path)
    try:
        yield
    finally:
        if os.path.exists(path):
            os.remove(path)

def test_symlink() -> None:
    try:
        test_symlink_path = os.path.join(Paths.VAR, 'zulip-test-symlink')
        with removing(test_symlink_path):
            os.symlink(os.path.join(Paths.ZULIP, 'README.md'), test_symlink_path)
    except OSError as err:
        print(FAIL + "Error: Unable to create symlinks."
              "Make sure you have permission to create symbolic links." + ENDC)
        print("See this page for more information:")
        print("  https://zulip.readthedocs.io/en/latest/development/setup-vagrant.html#os-symlink-error")
        raise RuntimeError() from err


def check_prerequisites() -> None:
    # check .git
    if not os.path.exists(os.path.join(Paths.ZULIP, ".git")):
        print("To setup the Zulip development environment, you should clone "
              "the code from GitHub, rather than using a Zulip production "
              "release tarball.")
        raise RuntimeError(FAIL + "No Zulip git repository present!" + ENDC)

    # Check the RAM on the user's system, and throw an effort if <1.5GB.
    # This avoids users getting segfaults running `pip install` that are
    # generally more annoying to debug.
    ram_gb = ram_size_gb()
    if ram_gb < 1.5:
        print("You have insufficient RAM (%d GB) to run the Zulip development "
              "environment." % round(ram_gb, 2))
        print("We recommend at least 2 GB of RAM, and require at least 1.5 GB.")
        raise RuntimeError()

    # check x86/64 platform
    check_platform()
    # test symlink permissions
    test_symlink()

UUID_VAR_PATH = get_dev_uuid_var_path(create_if_missing=True)
run(["mkdir", "-p", UUID_VAR_PATH])


# LOUD = dict(_out=sys.stdout, _err=sys.stderr)

user_id = os.getuid()

def setup_shell_profile(shell_profile: str) -> None:
    shell_profile_path = os.path.expanduser(shell_profile)

    def write_command(command: str) -> None:
        if os.path.exists(shell_profile_path):
            with open(shell_profile_path, 'r') as shell_profile_file:
                lines = [line.strip() for line in shell_profile_file.readlines()]
            if command not in lines:
                with open(shell_profile_path, 'a+') as shell_profile_file:
                    shell_profile_file.writelines(command + '\n')
        else:
            with open(shell_profile_path, 'w') as shell_profile_file:
                shell_profile_file.writelines(command + '\n')

    source_activate_command = "source " + os.path.join(Paths.VENV, "bin", "activate")
    write_command(source_activate_command)
    # FIXME: hard-coded path
    write_command('cd /srv/zulip')

def install_apt_deps() -> None:
    # setup Zulip-specific apt repos, and run `apt-get update`
    run(["sudo", "./scripts/lib/setup-apt-repo"])
    # remove duplicates.
    dep_list = sorted(set(Deps.APT))
    run(["sudo", "apt-get", "-y", "install", "--no-install-recommends"] + dep_list)


def install_node_modules() -> None:
    """Here we install node and the modules."""
    run(["sudo", "scripts/lib/install-node"])

    # This is a wrapper around `yarn`, which we run last since
    # it can often fail due to network issues beyond our control.
    try:
        # Hack: We remove `node_modules` as root to work around an
        # issue with the symlinks being improperly owned by root.
        if os.path.islink("node_modules"):
            run(["sudo", "rm", "-f", "node_modules"])
        run(["sudo", "mkdir", "-p", Paths.NODE_MODULES_CACHE])
        run(["sudo", "chown", "%s:%s" % (user_id, user_id), Paths.NODE_MODULES_CACHE])
        setup_node_modules(prefer_offline=True)
    except CalledProcessError:
        print(WARNING + "`yarn install` failed; retrying..." + ENDC)
        setup_node_modules()


def make_directories() -> None:
    # create log directory `zulip/var/log`
    run(["mkdir", "-p", Paths.LOG])
    # create upload directory `zulip/var/uploads`
    run(["mkdir", "-p", Paths.UPLOAD])
    # create test upload directory `zulip/var/test_upload`
    run(["mkdir", "-p", Paths.TEST_UPLOAD])
    # create coverage directory `zulip/var/coverage`
    run(["mkdir", "-p", Paths.COVERAGE])
    # create linecoverage directory `zulip/var/linecoverage-report`
    run(["mkdir", "-p", Paths.LINECOVERAGE])
    # create node coverage directory `zulip/var/node-coverage`
    run(["mkdir", "-p", Paths.NODE_COVERAGE])


def build_emoji() -> None:
    """Build emoji."""
    # `build_emoji` script requires `emoji-datasource` package which we install
    # via npm and hence it should be executed after we are done installing npm
    # packages.
    if not os.path.isdir(Paths.EMOJI_CACHE):
        run(["sudo", "mkdir", Paths.EMOJI_CACHE])
    run(["sudo", "chown", "%s:%s" % (user_id, user_id), Paths.EMOJI_CACHE])
    run(["tools/setup/emoji/build_emoji"])


def restart_ci_services() -> None:
    run(["sudo", "service", "rabbitmq-server", "restart"])
    run(["sudo", "service", "redis-server", "restart"])
    run(["sudo", "service", "memcached", "restart"])
    run(["sudo", "service", "postgresql", "restart"])

def restart_docker_services() -> None:
    run(["sudo", "service", "rabbitmq-server", "restart"])
    run(["sudo", "pg_dropcluster", "--stop", Versions.POSTGRES, "main"])
    run(["sudo", "pg_createcluster", "-e", "utf8", "--start", Versions.POSTGRES, "main"])
    run(["sudo", "service", "redis-server", "restart"])
    run(["sudo", "service", "memcached", "restart"])


def configure_rabbit_mq() -> None:
    try:
        from zerver.lib.queue import SimpleQueueClient
        SimpleQueueClient()
        configured = True
    except Exception:
        configured = False

    if options.is_force or not configured:
        run(["scripts/setup/configure-rabbitmq"])
    else:
        print("RabbitMQ is already configured.")


def rebuild_database() -> None:
    # Need to set up Django before using is_template_database_current
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
    import django
    django.setup()
    from zerver.lib.test_fixtures import is_template_database_current

    migration_status_path = os.path.join(UUID_VAR_PATH, "migration_status_dev")
    if options.is_force or not is_template_database_current(
            migration_status=migration_status_path,
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


def compile_translations() -> None:
    # Consider updating generated translations data: both `.mo`
    # files and `language-options.json`.
    sha1sum = hashlib.sha1()
    paths = ['zerver/management/commands/compilemessages.py']
    paths += glob('static/locale/*/LC_MESSAGES/*.po')
    paths += glob('static/locale/*/translations.json')

    # FIXME: where are the file boundaries?
    for path in paths:
        with open(path, 'rb') as file_to_hash:
            sha1sum.update(file_to_hash.read())

    compilemessages_hash_path = os.path.join(UUID_VAR_PATH, "last_compilemessages_hash")
    new_hash = sha1sum.hexdigest()
    Path(compilemessages_hash_path).touch()
    with open(compilemessages_hash_path, 'r') as hash_file:
        old_hash = hash_file.read()

    if options.is_force or (new_hash != old_hash):
        with open(compilemessages_hash_path, 'w') as hash_file:
            hash_file.write(new_hash)
        run(["./manage.py", "compilemessages"])
    else:
        print("No need to run `manage.py compilemessages`.")


def really_deploy() -> None:
    # The following block is skipped for the production Travis
    # suite, because that suite doesn't make use of these elements
    # of the development environment (it just uses the development
    # environment to build a release tarball).
    configure_rabbit_mq()
    rebuild_database()
    compile_translations()
    # Creates realm internal bots if required.
    run(["./manage.py", "create_realm_internal_bots"])


def _calculate_apt_progress_signature() -> Tuple[Any, Any, Any]:
    # hash the apt dependencies
    sha_sum = hashlib.sha1()
    # FIXME: add \n to avoid name collision
    for apt_depedency in Deps.APT:
        sha_sum.update(apt_depedency.encode('utf8'))
    # hash the content of setup-apt-repo
    sha_sum.update(open('scripts/lib/setup-apt-repo', 'rb').read())
    new_hash = sha_sum.hexdigest()

    # get last dependency signature
    old_hash = None
    apt_hash_file_path = os.path.join(UUID_VAR_PATH, "apt_dependencies_hash")
    try:
        hash_file = open(apt_hash_file_path, 'r+')
        old_hash = hash_file.read()
    except IOError:
        Path(apt_hash_file_path).touch()
        hash_file = open(apt_hash_file_path, 'r+')
    return hash_file, new_hash, old_hash


def resume_apt_install() -> None:
    hash_file, new_hash, old_hash = _calculate_apt_progress_signature()
    if new_hash != old_hash:
        try:
            install_apt_deps()
        except CalledProcessError:
            # Might be a failure due to network connection issues. Retrying...
            print(WARNING + "`apt-get -y install` failed while installing dependencies; retrying..." + ENDC)
            # Since a common failure mode is for the caching in
            # `setup-apt-repo` to optimize the fast code path to skip
            # running `apt-get update` when the target apt repository
            # is out of date, we run it explicitly here so that we
            # recover automatically.
            run(['sudo', 'apt-get', 'update'])
            install_apt_deps()
        hash_file.write(new_hash)
    else:
        print("No changes to apt dependencies, so skipping apt operations.")


def main(options: Any) -> int:
    check_prerequisites()
    # change to the root of Zulip, since yarn and management commands expect to
    # be run from the root of the project.
    os.chdir(Paths.ZULIP)
    make_directories()
    resume_apt_install()
    install_node_modules()

    # Import tools/setup_venv.py instead of running it so that we get an
    # activated virtualenv for the rest of the provisioning process.
    from tools.setup import setup_venvs
    setup_venvs.main()

    setup_shell_profile('~/.bash_profile')
    setup_shell_profile('~/.zprofile')

    run(["sudo", "cp", Paths.REPO_STOPWORDS, Paths.TSEARCH_STOPWORDS])
    build_emoji()

    # copy over static files from the zulip_bots package
    run(["tools/setup/generate_zulip_bots_static_files"])

    run(["tools/generate-custom-icon-webfont"])
    run(["tools/setup/build_pygments_data"])
    run(["scripts/setup/generate_secrets.py", "--development"])
    run(["tools/update-authors-json", "--use-fixture"])
    run(["tools/inline-email-css"])

    if is_circleci or (is_travis and not options.is_production_travis):
        restart_ci_services()
    elif options.is_docker:
        restart_docker_services()

    if not options.is_production_travis:
        # instead of building a tarball, we deploy Zulip
        really_deploy()

    run(["scripts/lib/clean-unused-caches"])

    version_file = os.path.join(UUID_VAR_PATH, 'provision_version')
    print('writing to ' + version_file)
    with open(version_file, 'w') as f:
        f.write(Versions.PROVISION + '\n')

    print('\n' + OKBLUE + 'Zulip development environment setup succeeded!' + ENDC)
    return 0

if __name__ == "__main__":
    description = 'Provision script to install Zulip'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--force', action='store_true', dest='is_force',
                        default=False,
                        help="Ignore all provisioning optimizations.")

    parser.add_argument('--production-travis', action='store_true',
                        dest='is_production_travis',
                        default=False,
                        help="Provision for Travis with production settings.")

    parser.add_argument('--docker', action='store_true',
                        dest='is_docker',
                        default=False,
                        help="Provision for Docker.")

    options = parser.parse_args()
    sys.exit(main(options))

__all__ = ['main']
