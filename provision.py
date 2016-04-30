from __future__ import print_function
import os
import sys
import logging
import platform
import subprocess

os.environ["PYTHONUNBUFFERED"] = "y"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from zulip_tools import run

SUPPORTED_PLATFORMS = {
    "Ubuntu": [
        "trusty",
        "xenial",
    ],
}

VENV_PATH = "/srv/zulip-venv"
PY3_VENV_PATH = "/srv/zulip-py3-venv"
ZULIP_PATH = os.path.dirname(os.path.abspath(__file__))

if not os.path.exists(os.path.join(ZULIP_PATH, ".git")):
    print("Error: No Zulip git repository present!")
    print("To setup the Zulip development environment, you should clone the code")
    print("from GitHub, rather than using a Zulip production release tarball.")
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
vendor = subprocess.check_output(["lsb_release", "-is"]).strip()
codename = subprocess.check_output(["lsb_release", "-cs"]).strip()
if not (vendor in SUPPORTED_PLATFORMS and codename in SUPPORTED_PLATFORMS[vendor]):
    logging.critical("Unsupported platform: {} {}".format(vendor, codename))
    sys.exit(1)

POSTGRES_VERSION_MAP = {
    "trusty": "9.3",
    "xenial": "9.5",
}
POSTGRES_VERSION = POSTGRES_VERSION_MAP[codename]

UBUNTU_COMMON_APT_DEPENDENCIES = [
    "closure-compiler",
    "libfreetype6-dev",
    "libffi-dev",
    "memcached",
    "rabbitmq-server",
    "libldap2-dev",
    "redis-server",
    "postgresql-server-dev-all",
    "libmemcached-dev",
    "python-dev",
    "hunspell-en-us",
    "nodejs",
    "nodejs-legacy",
    "python-virtualenv",
    "supervisor",
    "git",
    "npm",
    "yui-compressor",
    "wget",
    "ca-certificates",      # Explicit dependency in case e.g. wget is already installed
    "puppet",               # Used by lint-all
    "gettext",              # Used by makemessages i18n
    "curl",                 # Used for fetching PhantomJS as wget occasionally fails on redirects
    "netcat",               # Used for flushing memcached
]

APT_DEPENDENCIES = {
    "trusty": UBUNTU_COMMON_APT_DEPENDENCIES + [
        "postgresql-9.3",
    ],
    "xenial": UBUNTU_COMMON_APT_DEPENDENCIES + [
        "postgresql-9.5",
    ],
}

# tsearch-extras is an extension to postgres's built-in full-text search.
# TODO: use a real APT repository
TSEARCH_URL_PATTERN = "https://github.com/zulip/zulip-dist-tsearch-extras/raw/master/{}_{}_{}.deb?raw=1"
TSEARCH_PACKAGE_NAME = "postgresql-%s-tsearch-extras" % (POSTGRES_VERSION,)
TSEARCH_VERSION = "0.1.3"
TSEARCH_URL = TSEARCH_URL_PATTERN.format(TSEARCH_PACKAGE_NAME, TSEARCH_VERSION, arch)
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

def main():
    run(["sudo", "apt-get", "update"])
    run(["sudo", "apt-get", "-y", "install"] + APT_DEPENDENCIES[codename])

    temp_deb_path = subprocess.check_output(["mktemp", "package_XXXXXX.deb", "--tmpdir"])
    run(["wget", "-O", temp_deb_path, TSEARCH_URL])
    run(["sudo", "dpkg", "--install", temp_deb_path])

    run(["sudo", "rm", "-rf", VENV_PATH])
    run(["sudo", "mkdir", "-p", VENV_PATH])
    run(["sudo", "chown", "{}:{}".format(os.getuid(), os.getgid()), VENV_PATH])

    run(["sudo", "rm", "-rf", PY3_VENV_PATH])
    run(["sudo", "mkdir", "-p", PY3_VENV_PATH])
    run(["sudo", "chown", "{}:{}".format(os.getuid(), os.getgid()), PY3_VENV_PATH])

    run(["virtualenv", VENV_PATH])
    run(["virtualenv", "-p", "python3", PY3_VENV_PATH])

    # Put Python virtualenv activation in our .bash_profile.
    with open(os.path.expanduser('~/.bash_profile'), 'w+') as bash_profile:
        bash_profile.writelines([
            "source .bashrc\n",
            "source %s\n" % (os.path.join(VENV_PATH, "bin", "activate"),),
        ])

    # Switch current Python context to the python3 virtualenv
    activate_this = os.path.join(PY3_VENV_PATH, "bin", "activate_this.py")
    execfile(activate_this, dict(__file__=activate_this))

    run(["pip", "install", "--upgrade", "pip"])
    # install requirement
    run(["pip", "install", "--no-deps", "--requirement",
         os.path.join(ZULIP_PATH, "tools", "py3_test_reqs.txt")])

    # Switch current Python context to the python2 virtualenv.
    activate_this = os.path.join(VENV_PATH, "bin", "activate_this.py")
    execfile(activate_this, dict(__file__=activate_this))

    run(["pip", "install", "--upgrade", "pip"])
    run(["pip", "install", "--no-deps", "--requirement",
         os.path.join(ZULIP_PATH, "requirements.txt")])

    run(["sudo", "cp", REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH])

    # npm install and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    run(["tools/install-phantomjs"])
    run(["tools/download-zxcvbn"])
    run(["tools/emoji_dump/build_emoji"])
    run(["scripts/setup/generate_secrets.py", "-d"])
    if "--travis" in sys.argv:
        run(["sudo", "service", "rabbitmq-server", "restart"])
        run(["sudo", "service", "redis-server", "restart"])
        run(["sudo", "service", "memcached", "restart"])
    elif "--docker" in sys.argv:
        run(["sudo", "service", "rabbitmq-server", "restart"])
        run(["sudo", "pg_dropcluster", "--stop", POSTGRES_VERSION, "main"])
        run(["sudo", "pg_createcluster", "-e", "utf8", "--start", POSTGRES_VERSION, "main"])
        run(["sudo", "service", "redis-server", "restart"])
        run(["sudo", "service", "memcached", "restart"])
    run(["scripts/setup/configure-rabbitmq"])
    run(["tools/postgres-init-dev-db"])
    run(["tools/do-destroy-rebuild-database"])
    run(["tools/postgres-init-test-db"])
    run(["tools/do-destroy-rebuild-test-database"])
    # Install the latest npm.
    run(["sudo", "npm", "install", "-g", "npm"])
    # Run npm install last because it can be flaky, and that way one
    # only needs to rerun `npm install` to fix the installation.
    run(["npm", "install"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
