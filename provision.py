from __future__ import print_function
import os
import sys
import logging
import platform

try:
    import sh
except ImportError:
    import pbs as sh

SUPPORTED_PLATFORMS = {
    "Ubuntu": [
        "trusty",
    ],
}

APT_DEPENDENCIES = {
    "trusty": [
        "closure-compiler",
        "libfreetype6-dev",
        "libffi-dev",
        "memcached",
        "rabbitmq-server",
        "libldap2-dev",
        "redis-server",
        "postgresql-server-dev-all",
        "libmemcached-dev",
        "postgresql-9.3",
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
}

VENV_PATH = "/srv/zulip-venv"
ZULIP_PATH = "/srv/zulip"

if not os.path.exists(os.path.join(os.path.dirname(__file__), ".git")):
    print("Error: No Zulip git repository present at /srv/zulip!")
    print("To setup the Zulip development environment, you should clone the code")
    print("from GitHub, rather than using a Zulip production release tarball.")
    sys.exit(1)

# TODO: Parse arguments properly
if "--travis" in sys.argv or "--docker" in sys.argv:
    ZULIP_PATH = "."

# tsearch-extras is an extension to postgres's built-in full-text search.
# TODO: use a real APT repository
TSEARCH_URL_PATTERN = "https://github.com/zulip/zulip-dist-tsearch-extras/raw/master/{}_{}_{}.deb?raw=1"
TSEARCH_PACKAGE_NAME = {
    "trusty": "postgresql-9.3-tsearch-extras"
}
TSEARCH_VERSION = "0.1.3"
# TODO: this path is platform-specific!
TSEARCH_STOPWORDS_PATH = "/usr/share/postgresql/9.3/tsearch_data/"
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
    log = logging.getLogger("zulip-provisioner")

    if platform.architecture()[0] == '64bit':
        arch = 'amd64'
    elif platform.architecture()[0] == '32bit':
        arch = "i386"
    else:
        log.critical("Only x86 is supported; ping zulip-devel@googlegroups.com if you want another architecture.")
        sys.exit(1)

    vendor, version, codename = platform.dist()

    if not (vendor in SUPPORTED_PLATFORMS and codename in SUPPORTED_PLATFORMS[vendor]):
        log.critical("Unsupported platform: {} {}".format(vendor, codename))

    with sh.sudo:
        sh.apt_get.update(**LOUD)

        sh.apt_get.install(*APT_DEPENDENCIES["trusty"], assume_yes=True, **LOUD)

    temp_deb_path = sh.mktemp("package_XXXXXX.deb", tmpdir=True)

    sh.wget(
        TSEARCH_URL_PATTERN.format(
            TSEARCH_PACKAGE_NAME["trusty"],
            TSEARCH_VERSION,
            arch,
        ),
        output_document=temp_deb_path,
        **LOUD
    )

    with sh.sudo:
        sh.dpkg("--install", temp_deb_path, **LOUD)

    # Install phantomjs
    os.system("./tools/install-phantomjs")

    with sh.sudo:
        sh.rm("-rf", VENV_PATH, **LOUD)
        sh.mkdir("-p", VENV_PATH, **LOUD)
        sh.chown("{}:{}".format(os.getuid(), os.getgid()), VENV_PATH, **LOUD)

    sh.virtualenv(VENV_PATH, **LOUD)

    # Add the ./tools and ./scripts/setup directories inside the repository root to
    # the system path; we'll reference them later.
    orig_path = os.environ["PATH"]
    os.environ["PATH"] = os.pathsep.join((
            os.path.join(ZULIP_PATH, "tools"),
            os.path.join(ZULIP_PATH, "scripts", "setup"),
            orig_path
    ))


    # Put Python virtualenv activation in our .bash_profile.
    with open(os.path.expanduser('~/.bash_profile'), 'w+') as bash_profile:
        bash_profile.writelines([
            "source .bashrc\n",
            "source %s\n" % (os.path.join(VENV_PATH, "bin", "activate"),),
        ])

    # Switch current Python context to the virtualenv.
    activate_this = os.path.join(VENV_PATH, "bin", "activate_this.py")
    execfile(activate_this, dict(__file__=activate_this))

    sh.pip.install(requirement=os.path.join(ZULIP_PATH, "requirements.txt"), **LOUD)

    with sh.sudo:
        sh.cp(REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH, **LOUD)

    # npm install and management commands expect to be run from the root of the
    # project.
    os.chdir(ZULIP_PATH)

    os.system("tools/download-zxcvbn")
    os.system("tools/emoji_dump/build_emoji")
    os.system("generate_secrets.py -d")
    if "--travis" in sys.argv:
        os.system("sudo service rabbitmq-server restart")
        os.system("sudo service redis-server restart")
        os.system("sudo service memcached restart")
    elif "--docker" in sys.argv:
        os.system("sudo service rabbitmq-server restart")
        os.system("sudo pg_dropcluster --stop 9.3 main")
        os.system("sudo pg_createcluster -e utf8 --start 9.3 main")
        os.system("sudo service redis-server restart")
        os.system("sudo service memcached restart")
    sh.configure_rabbitmq(**LOUD)
    sh.postgres_init_dev_db(**LOUD)
    sh.do_destroy_rebuild_database(**LOUD)
    sh.postgres_init_test_db(**LOUD)
    sh.do_destroy_rebuild_test_database(**LOUD)
    # Run npm install last because it can be flaky, and that way one
    # only needs to rerun `npm install` to fix the installation.
    sh.npm.install(**LOUD)
    return 0

if __name__ == "__main__":
    sys.exit(main())
