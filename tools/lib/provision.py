#!/usr/bin/env python3
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
from scripts.lib.zulip_tools import run, run_as_root, OKBLUE, ENDC, WARNING, \
    get_dev_uuid_var_path, FAIL, parse_lsb_release, file_or_package_hash_updated
from scripts.lib.setup_venv import (
    VENV_DEPENDENCIES, REDHAT_VENV_DEPENDENCIES,
    THUMBOR_VENV_DEPENDENCIES, YUM_THUMBOR_VENV_DEPENDENCIES,
    FEDORA_VENV_DEPENDENCIES
)
from scripts.lib.node_cache import setup_node_modules, NODE_MODULES_CACHE_PATH

from version import PROVISION_VERSION
if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import Any, List

from tools.setup.generate_zulip_bots_static_files import generate_zulip_bots_static_files

SUPPORTED_PLATFORMS = {
    "Ubuntu": [
        "trusty",
        "xenial",
        "bionic",
    ],
    "Debian": [
        "stretch",
    ],
    "CentOS": [
        "centos7",
    ],
    "Fedora": [
        "fedora29",
    ],
    "RedHat": [
        "rhel7",
    ]
}

VENV_PATH = "/srv/zulip-py3-venv"
VAR_DIR_PATH = os.path.join(ZULIP_PATH, 'var')
LOG_DIR_PATH = os.path.join(VAR_DIR_PATH, 'log')
UPLOAD_DIR_PATH = os.path.join(VAR_DIR_PATH, 'uploads')
TEST_UPLOAD_DIR_PATH = os.path.join(VAR_DIR_PATH, 'test_uploads')
COVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'coverage')
NODE_TEST_COVERAGE_DIR_PATH = os.path.join(VAR_DIR_PATH, 'node-coverage')

is_travis = 'TRAVIS' in os.environ
is_circleci = 'CIRCLECI' in os.environ

# TODO: De-duplicate this with emoji_dump.py
EMOJI_CACHE_PATH = "/srv/zulip-emoji-cache"
if is_travis:
    # In Travis CI, we don't have root access
    EMOJI_CACHE_PATH = "/home/travis/zulip-emoji-cache"

if not os.path.exists(os.path.join(ZULIP_PATH, ".git")):
    print(FAIL + "Error: No Zulip git repository present!" + ENDC)
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
    UUID_VAR_PATH = get_dev_uuid_var_path(create_if_missing=True)
    os.makedirs(UUID_VAR_PATH, exist_ok=True)
    if os.path.exists(os.path.join(VAR_DIR_PATH, 'zulip-test-symlink')):
        os.remove(os.path.join(VAR_DIR_PATH, 'zulip-test-symlink'))
    os.symlink(
        os.path.join(ZULIP_PATH, 'README.md'),
        os.path.join(VAR_DIR_PATH, 'zulip-test-symlink')
    )
    os.remove(os.path.join(VAR_DIR_PATH, 'zulip-test-symlink'))
except OSError:
    print(FAIL + "Error: Unable to create symlinks."
          "Make sure you have permission to create symbolic links." + ENDC)
    print("See this page for more information:")
    print("  https://zulip.readthedocs.io/en/latest/development/setup-vagrant.html#os-symlink-error")
    sys.exit(1)

if platform.architecture()[0] == '64bit':
    arch = 'amd64'
elif platform.architecture()[0] == '32bit':
    arch = "i386"
else:
    logging.critical("Only x86 is supported;"
                     "ping zulip-devel@googlegroups.com if you want another architecture.")
    sys.exit(1)

# Ideally we wouldn't need to install a dependency here, before we
# know the codename.
is_rhel_based = os.path.exists("/etc/redhat-release")
if (not is_rhel_based) and (not os.path.exists("/usr/bin/lsb_release")):
    run_as_root(["apt-get", "install", "-y", "lsb-release"])

distro_info = parse_lsb_release()
vendor = distro_info['DISTRIB_ID']
codename = distro_info['DISTRIB_CODENAME']
family = distro_info['DISTRIB_FAMILY']
if not (vendor in SUPPORTED_PLATFORMS and codename in SUPPORTED_PLATFORMS[vendor]):
    logging.critical("Unsupported platform: {} {}".format(vendor, codename))
    sys.exit(1)

POSTGRES_VERSION_MAP = {
    "stretch": "9.6",
    "trusty": "9.3",
    "xenial": "9.5",
    "bionic": "10",
    "centos7": "10",
    "fedora29": "10",
    "rhel7": "10",
}
POSTGRES_VERSION = POSTGRES_VERSION_MAP[codename]

COMMON_DEPENDENCIES = [
    "closure-compiler",
    "memcached",
    "rabbitmq-server",
    "supervisor",
    "git",
    "wget",
    "ca-certificates",      # Explicit dependency in case e.g. wget is already installed
    "puppet",               # Used by lint (`puppet parser validate`)
    "gettext",              # Used by makemessages i18n
    "curl",                 # Used for fetching PhantomJS as wget occasionally fails on redirects
    "moreutils",            # Used for sponge command
]

UBUNTU_COMMON_APT_DEPENDENCIES = COMMON_DEPENDENCIES + [
    "redis-server",
    "hunspell-en-us",
    "yui-compressor",
    "puppet-lint",
    "netcat",               # Used for flushing memcached
    "libfontconfig1",       # Required by phantomjs
] + VENV_DEPENDENCIES + THUMBOR_VENV_DEPENDENCIES

COMMON_YUM_DEPENDENCIES = COMMON_DEPENDENCIES + [
    "redis",
    "hunspell-en-US",
    "yuicompressor",
    "rubygem-puppet-lint",
    "nmap-ncat",
    "fontconfig",  # phantomjs dependencies from here until libstdc++
    "freetype",
    "freetype-devel",
    "fontconfig-devel",
    "libstdc++"
] + YUM_THUMBOR_VENV_DEPENDENCIES

if vendor in ["Ubuntu", "Debian"]:
    SYSTEM_DEPENDENCIES = UBUNTU_COMMON_APT_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql-{0}",
            "postgresql-{0}-tsearch-extras",
            "postgresql-{0}-pgroonga",
        ]
    ]
elif vendor in ["CentOS", "RedHat"]:
    SYSTEM_DEPENDENCIES = COMMON_YUM_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql{0}-server",
            "postgresql{0}",
            "postgresql{0}-devel",
            "postgresql{0}-pgroonga",
        ]
    ] + REDHAT_VENV_DEPENDENCIES
elif vendor == "Fedora":
    SYSTEM_DEPENDENCIES = COMMON_YUM_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql{0}-server",
            "postgresql{0}",
            "postgresql{0}-devel",
        ]
    ] + FEDORA_VENV_DEPENDENCIES

if family == 'redhat':
    TSEARCH_STOPWORDS_PATH = "/usr/pgsql-%s/share/tsearch_data/" % (POSTGRES_VERSION,)
else:
    TSEARCH_STOPWORDS_PATH = "/usr/share/postgresql/%s/tsearch_data/" % (POSTGRES_VERSION,)
REPO_STOPWORDS_PATH = os.path.join(
    ZULIP_PATH,
    "puppet",
    "zulip",
    "files",
    "postgresql",
    "zulip_english.stop",
)

user_id = os.getuid()

def setup_shell_profile(shell_profile):
    # type: (str) -> None
    shell_profile_path = os.path.expanduser(shell_profile)

    def write_command(command):
        # type: (str) -> None
        if os.path.exists(shell_profile_path):
            with open(shell_profile_path, 'r') as shell_profile_file:
                lines = [line.strip() for line in shell_profile_file.readlines()]
            if command not in lines:
                with open(shell_profile_path, 'a+') as shell_profile_file:
                    shell_profile_file.writelines(command + '\n')
        else:
            with open(shell_profile_path, 'w') as shell_profile_file:
                shell_profile_file.writelines(command + '\n')

    source_activate_command = "source " + os.path.join(VENV_PATH, "bin", "activate")
    write_command(source_activate_command)
    write_command('cd /srv/zulip')

def install_system_deps(retry=False):
    # type: (bool) -> None

    # By doing list -> set -> list conversion, we remove duplicates.
    deps_to_install = list(set(SYSTEM_DEPENDENCIES))

    if family == 'redhat':
        install_yum_deps(deps_to_install, retry=retry)
        return

    if vendor in ["Debian", "Ubuntu"]:
        install_apt_deps(deps_to_install, retry=retry)
        return

    raise AssertionError("Invalid vendor")

def install_apt_deps(deps_to_install, retry=False):
    # type: (List[str], bool) -> None
    if retry:
        print(WARNING + "`apt-get -y install` failed while installing dependencies; retrying..." + ENDC)
        # Since a common failure mode is for the caching in
        # `setup-apt-repo` to optimize the fast code path to skip
        # running `apt-get update` when the target apt repository
        # is out of date, we run it explicitly here so that we
        # recover automatically.
        run_as_root(['apt-get', 'update'])

    # setup-apt-repo does an `apt-get update`
    run_as_root(["./scripts/lib/setup-apt-repo"])
    run_as_root(["apt-get", "-y", "install", "--no-install-recommends"] + deps_to_install)

def install_yum_deps(deps_to_install, retry=False):
    # type: (List[str], bool) -> None
    print(WARNING + "RedHat support is still experimental.")
    run_as_root(["./scripts/lib/setup-yum-repo"])

    # Hack specific to unregistered RHEL system.  The moreutils
    # package requires a perl module package, which isn't available in
    # the unregistered RHEL repositories.
    #
    # Error: Package: moreutils-0.49-2.el7.x86_64 (epel)
    #        Requires: perl(IPC::Run)
    yum_extra_flags = []  # type: List[str]
    if vendor == 'RedHat':
        exitcode, subs_status = subprocess.getstatusoutput("sudo subscription-manager status")
        if exitcode == 1:
            # TODO this might overkill since `subscription-manager` is already
            # called in setup-yum-repo
            if 'Status' in subs_status:
                # The output is well-formed
                yum_extra_flags = ["--skip-broken"]
            else:
                print("Unrecognized output. `subscription-manager` might not be available")

    run_as_root(["yum", "install", "-y"] + yum_extra_flags + deps_to_install)
    if vendor in ["CentOS", "RedHat"]:
        # This is how a pip3 is installed to /usr/bin in CentOS/RHEL
        # for python35 and later.
        run_as_root(["python36", "-m", "ensurepip"])
        # `python36` is not aliased to `python3` by default
        run_as_root(["ln", "-nsf", "/usr/bin/python36", "/usr/bin/python3"])
    postgres_dir = 'pgsql-%s' % (POSTGRES_VERSION,)
    for cmd in ['pg_config', 'pg_isready', 'psql']:
        # Our tooling expects these postgres scripts to be at
        # well-known paths.  There's an argument for eventually
        # making our tooling auto-detect, but this is simpler.
        run_as_root(["ln", "-nsf", "/usr/%s/bin/%s" % (postgres_dir, cmd),
                     "/usr/bin/%s" % (cmd,)])
    # Compile tsearch-extras from scratch, since we maintain the
    # package and haven't built an RPM package for it.
    run_as_root(["./scripts/lib/build-tsearch-extras"])
    if vendor == "Fedora":
        # Compile PGroonga from scratch, since pgroonga upstream
        # doesn't provide Fedora packages.
        run_as_root(["./scripts/lib/build-pgroonga"])

    # From here, we do the first-time setup/initialization for the postgres database.
    pg_datadir = "/var/lib/pgsql/%s/data" % (POSTGRES_VERSION,)
    pg_hba_conf = os.path.join(pg_datadir, "pg_hba.conf")

    # We can't just check if the file exists with os.path, since the
    # current user likely doesn't have permission to read the
    # pg_datadir directory.
    if subprocess.call(["sudo", "test", "-e", pg_hba_conf]) == 0:
        # Skip setup if it has been applied previously
        return

    run_as_root(["/usr/%s/bin/postgresql-%s-setup" % (postgres_dir, POSTGRES_VERSION), "initdb"],
                sudo_args = ['-H'])
    # Use vendored pg_hba.conf, which enables password authentication.
    run_as_root(["cp", "-a", "puppet/zulip/files/postgresql/centos_pg_hba.conf", pg_hba_conf])
    # Later steps will ensure postgres is started

def main(options):
    # type: (Any) -> int

    # yarn and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    # hash the apt dependencies
    sha_sum = hashlib.sha1()

    for apt_depedency in SYSTEM_DEPENDENCIES:
        sha_sum.update(apt_depedency.encode('utf8'))
    if vendor in ["Ubuntu", "Debian"]:
        sha_sum.update(open('scripts/lib/setup-apt-repo', 'rb').read())
    else:
        # hash the content of setup-yum-repo and build-*
        sha_sum.update(open('scripts/lib/setup-yum-repo', 'rb').read())
        build_paths = glob.glob("scripts/lib/build-")
        for bp in build_paths:
            sha_sum.update(open(bp, 'rb').read())

    new_apt_dependencies_hash = sha_sum.hexdigest()
    last_apt_dependencies_hash = None
    apt_hash_file_path = os.path.join(UUID_VAR_PATH, "apt_dependencies_hash")
    with open(apt_hash_file_path, 'a+') as hash_file:
        hash_file.seek(0)
        last_apt_dependencies_hash = hash_file.read()

    if (new_apt_dependencies_hash != last_apt_dependencies_hash):
        try:
            install_system_deps()
        except subprocess.CalledProcessError:
            # Might be a failure due to network connection issues. Retrying...
            install_system_deps(retry=True)
        with open(apt_hash_file_path, 'w') as hash_file:
            hash_file.write(new_apt_dependencies_hash)
    else:
        print("No changes to apt dependencies, so skipping apt operations.")

    # Here we install node.
    proxy_env = [
        "env",
        "http_proxy=" + os.environ.get("http_proxy", ""),
        "https_proxy=" + os.environ.get("https_proxy", ""),
        "no_proxy=" + os.environ.get("no_proxy", ""),
    ]
    run_as_root(proxy_env + ["scripts/lib/install-node"], sudo_args = ['-H'])

    # This is a wrapper around `yarn`, which we run last since
    # it can often fail due to network issues beyond our control.
    try:
        # Hack: We remove `node_modules` as root to work around an
        # issue with the symlinks being improperly owned by root.
        if os.path.islink("node_modules"):
            run_as_root(["rm", "-f", "node_modules"])
        run_as_root(["mkdir", "-p", NODE_MODULES_CACHE_PATH])
        run_as_root(["chown", "%s:%s" % (user_id, user_id), NODE_MODULES_CACHE_PATH])
        setup_node_modules(prefer_offline=True)
    except subprocess.CalledProcessError:
        print(WARNING + "`yarn install` failed; retrying..." + ENDC)
        setup_node_modules()

    # Install shellcheck.
    run_as_root(["scripts/lib/install-shellcheck"])

    from tools.setup import setup_venvs
    setup_venvs.main()

    activate_this = "/srv/zulip-py3-venv/bin/activate_this.py"
    exec(open(activate_this).read(), {}, dict(__file__=activate_this))

    setup_shell_profile('~/.bash_profile')
    setup_shell_profile('~/.zprofile')

    # This needs to happen before anything that imports zproject.settings.
    run(["scripts/setup/generate_secrets.py", "--development"])

    run_as_root(["cp", REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH])

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

    # The `build_emoji` script requires `emoji-datasource` package
    # which we install via npm; thus this step is after installing npm
    # packages.
    if not os.path.isdir(EMOJI_CACHE_PATH):
        run_as_root(["mkdir", EMOJI_CACHE_PATH])
    run_as_root(["chown", "%s:%s" % (user_id, user_id), EMOJI_CACHE_PATH])
    run(["tools/setup/emoji/build_emoji"])

    # copy over static files from the zulip_bots package
    generate_zulip_bots_static_files()

    webfont_paths = ["tools/setup/generate-custom-icon-webfont", "static/icons/fonts/template.hbs"]
    webfont_paths += glob.glob('static/assets/icons/*')
    if file_or_package_hash_updated(webfont_paths, "webfont_files_hash", options.is_force):
        run(["tools/setup/generate-custom-icon-webfont"])
    else:
        print("No need to run `tools/setup/generate-custom-icon-webfont`.")

    build_pygments_data_paths = ["tools/setup/build_pygments_data", "tools/setup/lang.json"]
    from pygments import __version__ as pygments_version
    if file_or_package_hash_updated(build_pygments_data_paths, "build_pygments_data_hash", options.is_force,
                                    [pygments_version]):
        run(["tools/setup/build_pygments_data"])
    else:
        print("No need to run `tools/setup/build_pygments_data`.")

    update_authors_json_paths = ["tools/update-authors-json", "zerver/tests/fixtures/authors.json"]
    if file_or_package_hash_updated(update_authors_json_paths, "update_authors_json_hash", options.is_force):
        run(["tools/update-authors-json", "--use-fixture"])
    else:
        print("No need to run `tools/update-authors-json`.")

    email_source_paths = ["tools/inline-email-css", "templates/zerver/emails/email.css"]
    email_source_paths += glob.glob('templates/zerver/emails/*.source.html')
    if file_or_package_hash_updated(email_source_paths, "last_email_source_files_hash", options.is_force):
        run(["tools/inline-email-css"])
    else:
        print("No need to run `tools/inline-email-css`.")

    if is_circleci or (is_travis and not options.is_production_travis):
        run_as_root(["service", "rabbitmq-server", "restart"])
        run_as_root(["service", "redis-server", "restart"])
        run_as_root(["service", "memcached", "restart"])
        run_as_root(["service", "postgresql", "restart"])
    elif family == 'redhat':
        for service in ["postgresql-%s" % (POSTGRES_VERSION,), "rabbitmq-server", "memcached", "redis"]:
            run_as_root(["systemctl", "enable", service], sudo_args = ['-H'])
            run_as_root(["systemctl", "start", service], sudo_args = ['-H'])
    elif options.is_docker:
        run_as_root(["service", "rabbitmq-server", "restart"])
        run_as_root(["pg_dropcluster", "--stop", POSTGRES_VERSION, "main"])
        run_as_root(["pg_createcluster", "-e", "utf8", "--start", POSTGRES_VERSION, "main"])
        run_as_root(["service", "redis-server", "restart"])
        run_as_root(["service", "memcached", "restart"])
    if not options.is_production_travis:
        # The following block is skipped for the production Travis
        # suite, because that suite doesn't make use of these elements
        # of the development environment (it just uses the development
        # environment to build a release tarball).

        # Need to set up Django before using template_database_status
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
        import django
        django.setup()

        from zerver.lib.test_fixtures import template_database_status, run_db_migrations

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

        migration_status_path = os.path.join(UUID_VAR_PATH, "migration_status_dev")
        dev_template_db_status = template_database_status(
            migration_status=migration_status_path,
            settings="zproject.settings",
            database_name="zulip",
        )
        if options.is_force or dev_template_db_status == 'needs_rebuild':
            run(["tools/setup/postgres-init-dev-db"])
            run(["tools/do-destroy-rebuild-database"])
        elif dev_template_db_status == 'run_migrations':
            run_db_migrations('dev')
        elif dev_template_db_status == 'current':
            print("No need to regenerate the dev DB.")

        test_template_db_status = template_database_status()
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
        paths += glob.glob('static/locale/*/LC_MESSAGES/*.po')
        paths += glob.glob('static/locale/*/translations.json')

        if file_or_package_hash_updated(paths, "last_compilemessages_hash", options.is_force):
            run(["./manage.py", "compilemessages"])
        else:
            print("No need to run `manage.py compilemessages`.")

    run(["scripts/lib/clean-unused-caches"])

    version_file = os.path.join(UUID_VAR_PATH, 'provision_version')
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
