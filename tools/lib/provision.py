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
from scripts.lib.zulip_tools import run_as_root, ENDC, WARNING, \
    get_dev_uuid_var_path, FAIL, os_families, parse_os_release, \
    overwrite_symlink
from scripts.lib.setup_venv import (
    VENV_DEPENDENCIES, REDHAT_VENV_DEPENDENCIES,
    THUMBOR_VENV_DEPENDENCIES, YUM_THUMBOR_VENV_DEPENDENCIES,
    FEDORA_VENV_DEPENDENCIES
)
from scripts.lib.node_cache import setup_node_modules, NODE_MODULES_CACHE_PATH
from tools.setup import setup_venvs

from typing import List, TYPE_CHECKING
if TYPE_CHECKING:
    # typing_extensions might not be installed yet
    from typing_extensions import NoReturn

VAR_DIR_PATH = os.path.join(ZULIP_PATH, 'var')

is_travis = 'TRAVIS' in os.environ
is_circleci = 'CIRCLECI' in os.environ

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
                     " ask on chat.zulip.org if you want another architecture.")
    # Note: It's probably actually not hard to add additional
    # architectures.
    sys.exit(1)

distro_info = parse_os_release()
vendor = distro_info['ID']
os_version = distro_info['VERSION_ID']
if vendor == "debian" and os_version == "9":  # stretch
    POSTGRES_VERSION = "9.6"
elif vendor == "debian" and os_version == "10":  # buster
    POSTGRES_VERSION = "11"
elif vendor == "ubuntu" and os_version == "16.04":  # xenial
    POSTGRES_VERSION = "9.5"
elif vendor == "ubuntu" and os_version in ["18.04", "18.10"]:  # bionic, cosmic
    POSTGRES_VERSION = "10"
elif vendor == "ubuntu" and os_version == "19.04":  # disco
    POSTGRES_VERSION = "11"
elif vendor == "fedora" and os_version == "29":
    POSTGRES_VERSION = "10"
elif vendor == "rhel" and os_version.startswith("7."):
    POSTGRES_VERSION = "10"
elif vendor == "centos" and os_version == "7":
    POSTGRES_VERSION = "10"
else:
    logging.critical("Unsupported platform: {} {}".format(vendor, os_version))
    if vendor == 'ubuntu' and os_version == '14.04':
        print()
        print("Ubuntu Trusty reached end-of-life upstream and is no longer a supported platform for Zulip")
        if os.path.exists('/home/vagrant'):
            print("To upgrade, run `vagrant destroy`, and then recreate the Vagrant guest.\n")
            print("See: https://zulip.readthedocs.io/en/latest/development/setup-vagrant.html")
    sys.exit(1)

COMMON_DEPENDENCIES = [
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
    "unzip",                # Needed for Slack import
]

UBUNTU_COMMON_APT_DEPENDENCIES = COMMON_DEPENDENCIES + [
    "redis-server",
    "hunspell-en-us",
    "puppet-lint",
    "netcat",               # Used for flushing memcached
    "libfontconfig1",       # Required by phantomjs
    "default-jre-headless",  # Required by vnu-jar
] + VENV_DEPENDENCIES + THUMBOR_VENV_DEPENDENCIES

COMMON_YUM_DEPENDENCIES = COMMON_DEPENDENCIES + [
    "redis",
    "hunspell-en-US",
    "rubygem-puppet-lint",
    "nmap-ncat",
    "fontconfig",  # phantomjs dependencies from here until libstdc++
    "freetype",
    "freetype-devel",
    "fontconfig-devel",
    "libstdc++"
] + YUM_THUMBOR_VENV_DEPENDENCIES

BUILD_PGROONGA_FROM_SOURCE = False
if vendor == 'debian' and os_version in []:
    # For platforms without a pgroonga release, we need to build it
    # from source.
    BUILD_PGROONGA_FROM_SOURCE = True
    SYSTEM_DEPENDENCIES = UBUNTU_COMMON_APT_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql-{0}",
            # Dependency for building pgroonga from source
            "postgresql-server-dev-{0}",
            "libgroonga-dev",
            "libmsgpack-dev",
        ]
    ]
elif "debian" in os_families():
    SYSTEM_DEPENDENCIES = UBUNTU_COMMON_APT_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql-{0}",
            "postgresql-{0}-pgroonga",
        ]
    ]
elif "rhel" in os_families():
    SYSTEM_DEPENDENCIES = COMMON_YUM_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql{0}-server",
            "postgresql{0}",
            "postgresql{0}-pgroonga",
        ]
    ] + REDHAT_VENV_DEPENDENCIES
elif "fedora" in os_families():
    SYSTEM_DEPENDENCIES = COMMON_YUM_DEPENDENCIES + [
        pkg.format(POSTGRES_VERSION) for pkg in [
            "postgresql{0}-server",
            "postgresql{0}",
            "postgresql{0}-devel",
            # Needed to build pgroonga from source
            "groonga-devel",
            "msgpack-devel",
        ]
    ] + FEDORA_VENV_DEPENDENCIES
    BUILD_PGROONGA_FROM_SOURCE = True

if "fedora" in os_families():
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

def install_system_deps():
    # type: () -> None

    # By doing list -> set -> list conversion, we remove duplicates.
    deps_to_install = sorted(set(SYSTEM_DEPENDENCIES))

    if "fedora" in os_families():
        install_yum_deps(deps_to_install)
    elif "debian" in os_families():
        install_apt_deps(deps_to_install)
    else:
        raise AssertionError("Invalid vendor")

    # For some platforms, there aren't published pgroonga
    # packages available, so we build them from source.
    if BUILD_PGROONGA_FROM_SOURCE:
        run_as_root(["./scripts/lib/build-pgroonga"])

def install_apt_deps(deps_to_install):
    # type: (List[str]) -> None
    # setup-apt-repo does an `apt-get update`
    run_as_root(["./scripts/lib/setup-apt-repo"])
    run_as_root(
        [
            "env", "DEBIAN_FRONTEND=noninteractive",
            "apt-get", "-y", "install", "--no-install-recommends",
        ]
        + deps_to_install
    )

def install_yum_deps(deps_to_install):
    # type: (List[str]) -> None
    print(WARNING + "RedHat support is still experimental.")
    run_as_root(["./scripts/lib/setup-yum-repo"])

    # Hack specific to unregistered RHEL system.  The moreutils
    # package requires a perl module package, which isn't available in
    # the unregistered RHEL repositories.
    #
    # Error: Package: moreutils-0.49-2.el7.x86_64 (epel)
    #        Requires: perl(IPC::Run)
    yum_extra_flags = []  # type: List[str]
    if vendor == "rhel":
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
    if "rhel" in os_families():
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

    # Link in tsearch data files
    overwrite_symlink("/usr/share/myspell/en_US.dic", "/usr/pgsql-%s/share/tsearch_data/en_us.dict"
                      % (POSTGRES_VERSION,))
    overwrite_symlink("/usr/share/myspell/en_US.aff", "/usr/pgsql-%s/share/tsearch_data/en_us.affix"
                      % (POSTGRES_VERSION,))

def main(options):
    # type: (argparse.Namespace) -> NoReturn

    # yarn and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    # hash the apt dependencies
    sha_sum = hashlib.sha1()

    for apt_depedency in SYSTEM_DEPENDENCIES:
        sha_sum.update(apt_depedency.encode('utf8'))
    if "debian" in os_families():
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
            print(WARNING + "Installing system dependencies failed; retrying..." + ENDC)
            install_system_deps()
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

    if not os.access(NODE_MODULES_CACHE_PATH, os.W_OK):
        run_as_root(["mkdir", "-p", NODE_MODULES_CACHE_PATH])
        run_as_root(["chown", "%s:%s" % (os.getuid(), os.getgid()), NODE_MODULES_CACHE_PATH])

    # This is a wrapper around `yarn`, which we run last since
    # it can often fail due to network issues beyond our control.
    try:
        setup_node_modules(prefer_offline=True)
    except subprocess.CalledProcessError:
        print(WARNING + "`yarn install` failed; retrying..." + ENDC)
        try:
            setup_node_modules()
        except subprocess.CalledProcessError:
            print(FAIL +
                  "`yarn install` is failing; check your network connection (and proxy settings)."
                  + ENDC)
            sys.exit(1)

    # Install shellcheck.
    run_as_root(["tools/setup/install-shellcheck"])

    setup_venvs.main()

    run_as_root(["cp", REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH])

    if is_circleci or (is_travis and not options.is_production_travis):
        run_as_root(["service", "rabbitmq-server", "restart"])
        run_as_root(["service", "redis-server", "restart"])
        run_as_root(["service", "memcached", "restart"])
        run_as_root(["service", "postgresql", "restart"])
    elif "fedora" in os_families():
        # These platforms don't enable and start services on
        # installing their package, so we do that here.
        for service in ["postgresql-%s" % (POSTGRES_VERSION,), "rabbitmq-server", "memcached", "redis"]:
            run_as_root(["systemctl", "enable", service], sudo_args = ['-H'])
            run_as_root(["systemctl", "start", service], sudo_args = ['-H'])

    # If we imported modules after activating the virtualenv in this
    # Python process, they could end up mismatching with modules we’ve
    # already imported from outside the virtualenv.  That seems like a
    # bad idea, and empirically it can cause Python to segfault on
    # certain cffi-related imports.  Instead, start a new Python
    # process inside the virtualenv.
    activate_this = "/srv/zulip-py3-venv/bin/activate_this.py"
    provision_inner = os.path.join(ZULIP_PATH, "tools", "lib", "provision_inner.py")
    exec(open(activate_this).read(), dict(__file__=activate_this))
    os.execvp(
        provision_inner,
        [
            provision_inner,
            *(["--force"] if options.is_force else []),
            *(["--production-travis"] if options.is_production_travis else []),
        ]
    )

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

    options = parser.parse_args()
    main(options)
