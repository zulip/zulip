from __future__ import print_function
import os
import sys
import logging
import platform
import subprocess

os.environ["PYTHONUNBUFFERED"] = "y"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from zulip_tools import run
from scripts.lib.setup_venv import setup_virtualenv, VENV_DEPENDENCIES

SUPPORTED_PLATFORMS = {
    "Ubuntu": [
        "trusty",
        "xenial",
    ],
}

NPM_VERSION = '3.9.3'
VENV_PATH = "/srv/zulip-venv"
PY3_VENV_PATH = "/srv/zulip-py3-venv"
ZULIP_PATH = os.path.dirname(os.path.abspath(__file__))
TRAVIS_NODE_PATH = os.path.join(os.environ['HOME'], 'node')

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
    "memcached",
    "rabbitmq-server",
    "redis-server",
    "hunspell-en-us",
    "nodejs",
    "nodejs-legacy",
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
] + VENV_DEPENDENCIES

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

def setup_node_modules():
    # type: () -> None
    output = subprocess.check_output(['sha1sum', 'package.json'])
    sha1sum = output.split()[0]
    success_stamp = os.path.join('node_modules', '.npm-success-stamp', sha1sum)
    if not os.path.exists(success_stamp):
        print("Deleting cached version")
        run(["rm", "-rf", "node_modules"])
        print("Installing node modules")
        run(["npm", "install"])
        run(["mkdir", "-p", success_stamp])
    else:
        print("Using cached version of node_modules")

def install_npm():
    # type: () -> None
    if "--travis" not in sys.argv:
        if subprocess.check_output(['npm', '--version']).strip() != NPM_VERSION:
            run(["sudo", "npm", "install", "-g", "npm@{}".format(NPM_VERSION)])

        return

    run(['mkdir', '-p', TRAVIS_NODE_PATH])

    npm_exe = os.path.join(TRAVIS_NODE_PATH, 'bin', 'npm')
    travis_npm = subprocess.check_output(['which', 'npm']).strip()
    if os.path.exists(npm_exe):
        run(['sudo', 'ln', '-sf', npm_exe, travis_npm])

    version = subprocess.check_output(['npm', '--version']).strip()
    if os.path.exists(npm_exe) and version == NPM_VERSION:
        print("Using cached npm")
        return

    run(["npm", "install", "-g", "--prefix", TRAVIS_NODE_PATH, "npm@{}".format(NPM_VERSION)])
    run(['sudo', 'ln', '-sf', npm_exe, travis_npm])


def main():
    # type: () -> int
    run(["sudo", "apt-get", "update"])
    run(["sudo", "apt-get", "-y", "install", "--no-install-recommends"] + APT_DEPENDENCIES[codename])

    if subprocess.call(['dpkg', '-s', TSEARCH_PACKAGE_NAME]):
        temp_deb_path = subprocess.check_output(["mktemp", "package_XXXXXX.deb", "--tmpdir"])
        run(["wget", "-O", temp_deb_path, TSEARCH_URL])
        run(["sudo", "dpkg", "--install", temp_deb_path])

    setup_virtualenv(PY3_VENV_PATH,
                     os.path.join(ZULIP_PATH, "requirements", "mypy.txt"),
                     virtualenv_args=['-p', 'python3'])
    setup_virtualenv(VENV_PATH, os.path.join(ZULIP_PATH, "requirements", "dev.txt"))

    # Put Python2 virtualenv activation in our .bash_profile.
    with open(os.path.expanduser('~/.bash_profile'), 'w+') as bash_profile:
        bash_profile.writelines([
            "source .bashrc\n",
            "source %s\n" % (os.path.join(VENV_PATH, "bin", "activate"),),
        ])

    run(["sudo", "cp", REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH])

    # npm install and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    if "--travis" in sys.argv:
        run(["tools/setup/install-phantomjs", "--travis"])
    else:
        run(["tools/setup/install-phantomjs"])
    run(["tools/setup/download-zxcvbn"])
    run(["tools/setup/emoji_dump/build_emoji"])
    run(["scripts/setup/generate_secrets.py", "-d"])
    if "--travis" in sys.argv and '--production-travis' not in sys.argv:
        run(["sudo", "service", "rabbitmq-server", "restart"])
        run(["sudo", "service", "redis-server", "restart"])
        run(["sudo", "service", "memcached", "restart"])
    elif "--docker" in sys.argv:
        run(["sudo", "service", "rabbitmq-server", "restart"])
        run(["sudo", "pg_dropcluster", "--stop", POSTGRES_VERSION, "main"])
        run(["sudo", "pg_createcluster", "-e", "utf8", "--start", POSTGRES_VERSION, "main"])
        run(["sudo", "service", "redis-server", "restart"])
        run(["sudo", "service", "memcached", "restart"])
    if '--production-travis' not in sys.argv:
        # These won't be used anyway
        run(["scripts/setup/configure-rabbitmq"])
        run(["tools/setup/postgres-init-dev-db"])
        run(["tools/do-destroy-rebuild-database"])
        run(["tools/setup/postgres-init-test-db"])
        run(["tools/do-destroy-rebuild-test-database"])
        run(["python", "./manage.py", "compilemessages"])
    # Install the pinned version of npm.
    install_npm()
    # Run npm install last because it can be flaky, and that way one
    # only needs to rerun `npm install` to fix the installation.
    setup_node_modules()
    return 0

if __name__ == "__main__":
    sys.exit(main())
