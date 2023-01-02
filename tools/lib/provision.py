#!/usr/bin/env python3
import argparse
import hashlib
import logging
import os
import platform
import subprocess
import sys
from typing import List, NoReturn

os.environ["PYTHONUNBUFFERED"] = "y"

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.append(ZULIP_PATH)

from scripts.lib.node_cache import NODE_MODULES_CACHE_PATH, setup_node_modules
from scripts.lib.setup_venv import get_venv_dependencies
from scripts.lib.zulip_tools import (
    ENDC,
    FAIL,
    WARNING,
    get_dev_uuid_var_path,
    os_families,
    parse_os_release,
    run_as_root,
)
from tools.setup import setup_venvs

VAR_DIR_PATH = os.path.join(ZULIP_PATH, "var")

CONTINUOUS_INTEGRATION = "GITHUB_ACTIONS" in os.environ

if not os.path.exists(os.path.join(ZULIP_PATH, ".git")):
    print(FAIL + "Error: No Zulip Git repository present!" + ENDC)
    print("To set up the Zulip development environment, you should clone the code")
    print("from GitHub, rather than using a Zulip production release tarball.")
    sys.exit(1)

# Check the RAM on the user's system, and throw an effort if <1.5GB.
# This avoids users getting segfaults running `pip install` that are
# generally more annoying to debug.
with open("/proc/meminfo") as meminfo:
    ram_size = meminfo.readlines()[0].strip().split(" ")[-2]
ram_gb = float(ram_size) / 1024.0 / 1024.0
if ram_gb < 1.5:
    print(
        "You have insufficient RAM ({} GB) to run the Zulip development environment.".format(
            round(ram_gb, 2)
        )
    )
    print("We recommend at least 2 GB of RAM, and require at least 1.5 GB.")
    sys.exit(1)

try:
    UUID_VAR_PATH = get_dev_uuid_var_path(create_if_missing=True)
    os.makedirs(UUID_VAR_PATH, exist_ok=True)
    if os.path.exists(os.path.join(VAR_DIR_PATH, "zulip-test-symlink")):
        os.remove(os.path.join(VAR_DIR_PATH, "zulip-test-symlink"))
    os.symlink(
        os.path.join(ZULIP_PATH, "README.md"),
        os.path.join(VAR_DIR_PATH, "zulip-test-symlink"),
    )
    os.remove(os.path.join(VAR_DIR_PATH, "zulip-test-symlink"))
except OSError:
    print(
        FAIL + "Error: Unable to create symlinks. "
        "Make sure you have permission to create symbolic links." + ENDC
    )
    print("See this page for more information:")
    print(
        "  https://zulip.readthedocs.io/en/latest/development/setup-recommended.html#os-symlink-error"
    )
    sys.exit(1)

distro_info = parse_os_release()
vendor = distro_info["ID"]
os_version = distro_info["VERSION_ID"]
if vendor == "debian" and os_version == "11":  # bullseye
    POSTGRESQL_VERSION = "13"
elif vendor == "ubuntu" and os_version == "20.04":  # focal
    POSTGRESQL_VERSION = "12"
elif vendor == "ubuntu" and os_version == "21.10":  # impish
    POSTGRESQL_VERSION = "13"
elif vendor == "ubuntu" and os_version == "22.04":  # jammy
    POSTGRESQL_VERSION = "14"
elif vendor == "neon" and os_version == "20.04":  # KDE Neon
    POSTGRESQL_VERSION = "12"
elif vendor == "fedora" and os_version == "33":
    POSTGRESQL_VERSION = "13"
elif vendor == "fedora" and os_version == "34":
    POSTGRESQL_VERSION = "13"
elif vendor == "rhel" and os_version.startswith("7."):
    POSTGRESQL_VERSION = "10"
elif vendor == "centos" and os_version == "7":
    POSTGRESQL_VERSION = "10"
else:
    logging.critical("Unsupported platform: %s %s", vendor, os_version)
    sys.exit(1)

VENV_DEPENDENCIES = get_venv_dependencies(vendor, os_version)

COMMON_DEPENDENCIES = [
    "memcached",
    "rabbitmq-server",
    "supervisor",
    "git",
    "curl",
    "ca-certificates",  # Explicit dependency in case e.g. curl is already installed
    "puppet",  # Used by lint (`puppet parser validate`)
    "gettext",  # Used by makemessages i18n
    "curl",  # Used for testing our API documentation
    "moreutils",  # Used for sponge command
    "unzip",  # Needed for Slack import
    "crudini",  # Used for shell tooling w/ zulip.conf
    # Puppeteer dependencies from here
    "xdg-utils",
    # Puppeteer dependencies end here.
]

UBUNTU_COMMON_APT_DEPENDENCIES = [
    *COMMON_DEPENDENCIES,
    "redis-server",
    "hunspell-en-us",
    "puppet-lint",
    "default-jre-headless",  # Required by vnu-jar
    # Puppeteer dependencies from here
    "fonts-freefont-ttf",
    "gconf-service",
    "libappindicator1",
    "libatk-bridge2.0-0",
    "libgbm1",
    "libgconf-2-4",
    "libgtk-3-0",
    "libx11-xcb1",
    "libxcb-dri3-0",
    "libxss1",
    "xvfb",
    # Puppeteer dependencies end here.
]

COMMON_YUM_DEPENDENCIES = [
    *COMMON_DEPENDENCIES,
    "redis",
    "hunspell-en-US",
    "rubygem-puppet-lint",
    "nmap-ncat",
    "ccache",  # Required to build pgroonga from source.
    # Puppeteer dependencies from here
    "at-spi2-atk",
    "GConf2",
    "gtk3",
    "libX11-xcb",
    "libxcb",
    "libXScrnSaver",
    "mesa-libgbm",
    "xorg-x11-server-Xvfb",
    # Puppeteer dependencies end here.
]

BUILD_PGROONGA_FROM_SOURCE = False
if vendor == "debian" and os_version in [] or vendor == "ubuntu" and os_version in []:
    # For platforms without a PGroonga release, we need to build it
    # from source.
    BUILD_PGROONGA_FROM_SOURCE = True
    SYSTEM_DEPENDENCIES = [
        *UBUNTU_COMMON_APT_DEPENDENCIES,
        f"postgresql-{POSTGRESQL_VERSION}",
        # Dependency for building PGroonga from source
        f"postgresql-server-dev-{POSTGRESQL_VERSION}",
        "libgroonga-dev",
        "libmsgpack-dev",
        "clang",
        *VENV_DEPENDENCIES,
    ]
elif "debian" in os_families():
    DEBIAN_DEPENDENCIES = UBUNTU_COMMON_APT_DEPENDENCIES
    # The below condition is required since libappindicator is
    # not available for Debian 11. "libgroonga1" is an
    # additional dependency for postgresql-13-pgdg-pgroonga.
    #
    # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=895037
    if vendor == "debian" and os_version == "11":
        DEBIAN_DEPENDENCIES.remove("libappindicator1")
        DEBIAN_DEPENDENCIES.append("libgroonga0")

    # If we are on an aarch64 processor, ninja will be built from source,
    # so cmake is required
    if platform.machine() == "aarch64":
        DEBIAN_DEPENDENCIES.append("cmake")

    SYSTEM_DEPENDENCIES = [
        *DEBIAN_DEPENDENCIES,
        f"postgresql-{POSTGRESQL_VERSION}",
        f"postgresql-{POSTGRESQL_VERSION}-pgroonga",
        *VENV_DEPENDENCIES,
    ]
elif "rhel" in os_families():
    SYSTEM_DEPENDENCIES = [
        *COMMON_YUM_DEPENDENCIES,
        f"postgresql{POSTGRESQL_VERSION}-server",
        f"postgresql{POSTGRESQL_VERSION}",
        f"postgresql{POSTGRESQL_VERSION}-devel",
        f"postgresql{POSTGRESQL_VERSION}-pgdg-pgroonga",
        *VENV_DEPENDENCIES,
    ]
elif "fedora" in os_families():
    SYSTEM_DEPENDENCIES = [
        *COMMON_YUM_DEPENDENCIES,
        f"postgresql{POSTGRESQL_VERSION}-server",
        f"postgresql{POSTGRESQL_VERSION}",
        f"postgresql{POSTGRESQL_VERSION}-devel",
        # Needed to build PGroonga from source
        "groonga-devel",
        "msgpack-devel",
        *VENV_DEPENDENCIES,
    ]
    BUILD_PGROONGA_FROM_SOURCE = True

if "fedora" in os_families():
    TSEARCH_STOPWORDS_PATH = f"/usr/pgsql-{POSTGRESQL_VERSION}/share/tsearch_data/"
else:
    TSEARCH_STOPWORDS_PATH = f"/usr/share/postgresql/{POSTGRESQL_VERSION}/tsearch_data/"
REPO_STOPWORDS_PATH = os.path.join(
    ZULIP_PATH,
    "puppet",
    "zulip",
    "files",
    "postgresql",
    "zulip_english.stop",
)


def install_system_deps() -> None:
    # By doing list -> set -> list conversion, we remove duplicates.
    deps_to_install = sorted(set(SYSTEM_DEPENDENCIES))

    if "fedora" in os_families():
        install_yum_deps(deps_to_install)
    elif "debian" in os_families():
        install_apt_deps(deps_to_install)
    else:
        raise AssertionError("Invalid vendor")

    # For some platforms, there aren't published PGroonga
    # packages available, so we build them from source.
    if BUILD_PGROONGA_FROM_SOURCE:
        run_as_root(["./scripts/lib/build-pgroonga"])


def install_apt_deps(deps_to_install: List[str]) -> None:
    # setup-apt-repo does an `apt-get update` if the sources.list files changed.
    run_as_root(["./scripts/lib/setup-apt-repo"])

    # But we still need to do our own to make sure we have up-to-date
    # data before installing new packages, as the system might not have
    # done an apt update in weeks otherwise, which could result in 404s
    # trying to download old versions that were already removed from mirrors.
    run_as_root(["apt-get", "update"])
    run_as_root(
        [
            "env",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "-y",
            "install",
            "--allow-downgrades",
            "--no-install-recommends",
            *deps_to_install,
        ]
    )


def install_yum_deps(deps_to_install: List[str]) -> None:
    print(WARNING + "RedHat support is still experimental." + ENDC)
    run_as_root(["./scripts/lib/setup-yum-repo"])

    # Hack specific to unregistered RHEL system.  The moreutils
    # package requires a perl module package, which isn't available in
    # the unregistered RHEL repositories.
    #
    # Error: Package: moreutils-0.49-2.el7.x86_64 (epel)
    #        Requires: perl(IPC::Run)
    yum_extra_flags: List[str] = []
    if vendor == "rhel":
        exitcode, subs_status = subprocess.getstatusoutput("sudo subscription-manager status")
        if exitcode == 1:
            # TODO this might overkill since `subscription-manager` is already
            # called in setup-yum-repo
            if "Status" in subs_status:
                # The output is well-formed
                yum_extra_flags = ["--skip-broken"]
            else:
                print("Unrecognized output. `subscription-manager` might not be available")

    run_as_root(["yum", "install", "-y", *yum_extra_flags, *deps_to_install])
    if "rhel" in os_families():
        # This is how a pip3 is installed to /usr/bin in CentOS/RHEL
        # for python35 and later.
        run_as_root(["python36", "-m", "ensurepip"])
        # `python36` is not aliased to `python3` by default
        run_as_root(["ln", "-nsf", "/usr/bin/python36", "/usr/bin/python3"])
    postgresql_dir = f"pgsql-{POSTGRESQL_VERSION}"
    for cmd in ["pg_config", "pg_isready", "psql"]:
        # Our tooling expects these PostgreSQL scripts to be at
        # well-known paths.  There's an argument for eventually
        # making our tooling auto-detect, but this is simpler.
        run_as_root(["ln", "-nsf", f"/usr/{postgresql_dir}/bin/{cmd}", f"/usr/bin/{cmd}"])

    # From here, we do the first-time setup/initialization for the PostgreSQL database.
    pg_datadir = f"/var/lib/pgsql/{POSTGRESQL_VERSION}/data"
    pg_hba_conf = os.path.join(pg_datadir, "pg_hba.conf")

    # We can't just check if the file exists with os.path, since the
    # current user likely doesn't have permission to read the
    # pg_datadir directory.
    if subprocess.call(["sudo", "test", "-e", pg_hba_conf]) == 0:
        # Skip setup if it has been applied previously
        return

    run_as_root(
        [f"/usr/{postgresql_dir}/bin/postgresql-{POSTGRESQL_VERSION}-setup", "initdb"],
        sudo_args=["-H"],
    )
    # Use vendored pg_hba.conf, which enables password authentication.
    run_as_root(["cp", "-a", "puppet/zulip/files/postgresql/centos_pg_hba.conf", pg_hba_conf])
    # Later steps will ensure PostgreSQL is started

    # Link in tsearch data files
    run_as_root(
        [
            "ln",
            "-nsf",
            "/usr/share/myspell/en_US.dic",
            f"/usr/pgsql-{POSTGRESQL_VERSION}/share/tsearch_data/en_us.dict",
        ]
    )
    run_as_root(
        [
            "ln",
            "-nsf",
            "/usr/share/myspell/en_US.aff",
            f"/usr/pgsql-{POSTGRESQL_VERSION}/share/tsearch_data/en_us.affix",
        ]
    )


def main(options: argparse.Namespace) -> NoReturn:
    # yarn and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    # hash the apt dependencies
    sha_sum = hashlib.sha1()

    for apt_dependency in SYSTEM_DEPENDENCIES:
        sha_sum.update(apt_dependency.encode())
    if "debian" in os_families():
        with open("scripts/lib/setup-apt-repo", "rb") as fb:
            sha_sum.update(fb.read())
    else:
        # hash the content of setup-yum-repo*
        with open("scripts/lib/setup-yum-repo", "rb") as fb:
            sha_sum.update(fb.read())

    # hash the content of build-pgroonga if PGroonga is built from source
    if BUILD_PGROONGA_FROM_SOURCE:
        with open("scripts/lib/build-pgroonga", "rb") as fb:
            sha_sum.update(fb.read())

    new_apt_dependencies_hash = sha_sum.hexdigest()
    last_apt_dependencies_hash = None
    apt_hash_file_path = os.path.join(UUID_VAR_PATH, "apt_dependencies_hash")
    with open(apt_hash_file_path, "a+") as hash_file:
        hash_file.seek(0)
        last_apt_dependencies_hash = hash_file.read()

    if new_apt_dependencies_hash != last_apt_dependencies_hash:
        try:
            install_system_deps()
        except subprocess.CalledProcessError:
            try:
                # Might be a failure due to network connection issues. Retrying...
                print(WARNING + "Installing system dependencies failed; retrying..." + ENDC)
                install_system_deps()
            except BaseException as e:
                # Suppress exception chaining
                raise e from None
        with open(apt_hash_file_path, "w") as hash_file:
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
    run_as_root([*proxy_env, "scripts/lib/install-node"], sudo_args=["-H"])
    run_as_root([*proxy_env, "scripts/lib/install-yarn"])

    if not os.access(NODE_MODULES_CACHE_PATH, os.W_OK):
        run_as_root(["mkdir", "-p", NODE_MODULES_CACHE_PATH])
        run_as_root(["chown", f"{os.getuid()}:{os.getgid()}", NODE_MODULES_CACHE_PATH])

    # This is a wrapper around `yarn`, which we run last since
    # it can often fail due to network issues beyond our control.
    try:
        setup_node_modules(prefer_offline=True)
    except subprocess.CalledProcessError:
        print(WARNING + "`yarn install` failed; retrying..." + ENDC)
        try:
            setup_node_modules()
        except subprocess.CalledProcessError:
            print(
                FAIL
                + "`yarn install` is failing; check your network connection (and proxy settings)."
                + ENDC
            )
            sys.exit(1)

    # Install shellcheck.
    run_as_root([*proxy_env, "tools/setup/install-shellcheck"])
    # Install shfmt.
    run_as_root([*proxy_env, "tools/setup/install-shfmt"])

    # Install transifex-cli.
    run_as_root([*proxy_env, "tools/setup/install-transifex-cli"])

    setup_venvs.main()

    run_as_root(["cp", REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH])

    if CONTINUOUS_INTEGRATION and not options.is_build_release_tarball_only:
        run_as_root(["service", "redis-server", "start"])
        run_as_root(["service", "memcached", "start"])
        run_as_root(["service", "rabbitmq-server", "start"])
        run_as_root(["service", "postgresql", "start"])
    elif "fedora" in os_families():
        # These platforms don't enable and start services on
        # installing their package, so we do that here.
        for service in [
            f"postgresql-{POSTGRESQL_VERSION}",
            "rabbitmq-server",
            "memcached",
            "redis",
        ]:
            run_as_root(["systemctl", "enable", service], sudo_args=["-H"])
            run_as_root(["systemctl", "start", service], sudo_args=["-H"])

    # If we imported modules after activating the virtualenv in this
    # Python process, they could end up mismatching with modules we’ve
    # already imported from outside the virtualenv.  That seems like a
    # bad idea, and empirically it can cause Python to segfault on
    # certain cffi-related imports.  Instead, start a new Python
    # process inside the virtualenv.
    activate_this = "/srv/zulip-py3-venv/bin/activate_this.py"
    provision_inner = os.path.join(ZULIP_PATH, "tools", "lib", "provision_inner.py")
    with open(activate_this) as f:
        exec(f.read(), dict(__file__=activate_this))
    os.execvp(
        provision_inner,
        [
            provision_inner,
            *(["--force"] if options.is_force else []),
            *(["--build-release-tarball-only"] if options.is_build_release_tarball_only else []),
            *(["--skip-dev-db-build"] if options.skip_dev_db_build else []),
        ],
    )


if __name__ == "__main__":
    description = "Provision script to install Zulip"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--force",
        action="store_true",
        dest="is_force",
        help="Ignore all provisioning optimizations.",
    )

    parser.add_argument(
        "--build-release-tarball-only",
        action="store_true",
        dest="is_build_release_tarball_only",
        help="Provision needed to build release tarball.",
    )

    parser.add_argument(
        "--skip-dev-db-build", action="store_true", help="Don't run migrations on dev database."
    )

    options = parser.parse_args()
    main(options)
