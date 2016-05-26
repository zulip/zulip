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
VENV_CACHE_PATH = "/srv/zulip-venv-cache"
if "--travis" in sys.argv:
    # In Travis CI, we don't have root access
    VENV_CACHE_PATH = os.path.join(os.environ['HOME'], "zulip-venv-cache")

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
    "python3-dev",          # Needed to install typed-ast dependency of mypy
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

def setup_virtualenv(target_venv_path, requirements_file, virtualenv_args=[]):
    # Check if a cached version already exists
    output = subprocess.check_output(['sha1sum', requirements_file])
    sha1sum = output.split()[0]
    cached_venv_path = os.path.join(VENV_CACHE_PATH, sha1sum, os.path.basename(target_venv_path))
    success_stamp = os.path.join(cached_venv_path, "success-stamp")
    if not os.path.exists(success_stamp):
        do_setup_virtualenv(cached_venv_path, requirements_file, virtualenv_args)
        run(["touch", success_stamp])

    print("Using cached Python venv from %s" % (cached_venv_path,))
    run(["sudo", "ln", "-nsf", cached_venv_path, target_venv_path])
    activate_this = os.path.join(target_venv_path, "bin", "activate_this.py")
    exec(open(activate_this).read(), {}, dict(__file__=activate_this)) # type: ignore # https://github.com/python/mypy/issues/1577

def do_setup_virtualenv(venv_path, requirements_file, virtualenv_args):
    # Setup Python virtualenv
    run(["sudo", "rm", "-rf", venv_path])
    run(["sudo", "mkdir", "-p", venv_path])
    run(["sudo", "chown", "{}:{}".format(os.getuid(), os.getgid()), venv_path])
    run(["virtualenv"] + virtualenv_args + [venv_path])

    # Switch current Python context to the virtualenv.
    activate_this = os.path.join(venv_path, "bin", "activate_this.py")
    exec(open(activate_this).read(), {}, dict(__file__=activate_this)) # type: ignore # https://github.com/python/mypy/issues/1577

    run(["pip", "install", "--upgrade", "pip"])
    run(["pip", "install", "--no-deps", "--requirement", requirements_file])

def main():
    run(["sudo", "apt-get", "update"])
    run(["sudo", "apt-get", "-y", "install"] + APT_DEPENDENCIES[codename])

    temp_deb_path = subprocess.check_output(["mktemp", "package_XXXXXX.deb", "--tmpdir"])
    run(["wget", "-O", temp_deb_path, TSEARCH_URL])
    run(["sudo", "dpkg", "--install", temp_deb_path])

    setup_virtualenv(PY3_VENV_PATH,
                     os.path.join(ZULIP_PATH, "tools", "setup", "py3_test_reqs.txt"),
                     virtualenv_args=['-p', 'python3'])
    setup_virtualenv(VENV_PATH, os.path.join(ZULIP_PATH, "requirements.txt"))

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
    run(["tools/setup/postgres-init-dev-db"])
    run(["tools/do-destroy-rebuild-database"])
    run(["tools/setup/postgres-init-test-db"])
    run(["tools/do-destroy-rebuild-test-database"])
    run(["python", "./manage.py", "compilemessages"])
    # Install the latest npm.
    run(["sudo", "npm", "install", "-g", "npm"])
    # Run npm install last because it can be flaky, and that way one
    # only needs to rerun `npm install` to fix the installation.
    run(["npm", "install"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
