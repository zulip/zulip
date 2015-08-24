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
        "python-virtualenv",
        "supervisor",
        "git",
        "npm",
        "node-jquery",
        "yui-compressor",
        "puppet",               # Used by lint-all
    ]
}

# TODO: backport node-{cssstyle,htmlparser2,nwmatcher} to trusty,
# so we can eliminate npm (above) and this section.
NPM_DEPENDENCIES = {
    "trusty": [
        "cssstyle",
        "htmlparser2",
        "nwmatcher",
    ]
}

VENV_PATH="/srv/zulip-venv"
ZULIP_PATH="/srv/zulip"

# tsearch-extras is an extension to postgres's built-in full-text search.
# TODO: use a real APT repository
TSEARCH_URL_BASE = "https://dl.dropboxusercontent.com/u/283158365/zuliposs/"
TSEARCH_PACKAGE_NAME = {
    "trusty": "postgresql-9.3-tsearch-extras"
}
TSEARCH_VERSION = "0.1.2"
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
    # TODO: support other architectures
    if platform.architecture()[0] == '64bit':
        arch = 'amd64'
    else:
        log.critical("Only amd64 is supported.")

    vendor, version, codename = platform.dist()

    if not (vendor in SUPPORTED_PLATFORMS and codename in SUPPORTED_PLATFORMS[vendor]):
        log.critical("Unsupported platform: {} {}".format(vendor, codename))

    with sh.sudo:
        sh.apt_get.update(**LOUD)

        sh.apt_get.install(*APT_DEPENDENCIES["trusty"], assume_yes=True, **LOUD)

    temp_deb_path = sh.mktemp("package_XXXXXX.deb", tmpdir=True)

    sh.wget(
        "{}/{}_{}_{}.deb".format(
            TSEARCH_URL_BASE,
            TSEARCH_PACKAGE_NAME["trusty"],
            TSEARCH_VERSION,
            arch,
        ),
        output_document=temp_deb_path,
        **LOUD
    )

    with sh.sudo:
        sh.dpkg("--install", temp_deb_path, **LOUD)

    with sh.sudo:
        PHANTOMJS_PATH = "/srv/phantomjs"
        PHANTOMJS_TARBALL = os.path.join(PHANTOMJS_PATH, "phantomjs-1.9.8-linux-x86_64.tar.bz2")
        sh.mkdir("-p", PHANTOMJS_PATH, **LOUD)
        sh.wget("https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-1.9.8-linux-x86_64.tar.bz2",
                output_document=PHANTOMJS_TARBALL, **LOUD)
        sh.tar("xj", directory=PHANTOMJS_PATH, file=PHANTOMJS_TARBALL, **LOUD)
        sh.ln("-sf", os.path.join(PHANTOMJS_PATH, "phantomjs-1.9.8-linux-x86_64", "bin", "phantomjs"),
              "/usr/local/bin/phantomjs", **LOUD)

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

    # Add additional node packages for test-js-with-node.
    with sh.sudo:
        sh.npm.install(*NPM_DEPENDENCIES["trusty"], g=True, prefix="/usr", **LOUD)

    # Management commands expect to be run from the root of the project.
    os.chdir(ZULIP_PATH)

    os.system("generate_secrets.py -d")
    sh.configure_rabbitmq(**LOUD)
    sh.postgres_init_db(**LOUD)
    sh.do_destroy_rebuild_database(**LOUD)
    sh.postgres_init_test_db(**LOUD)
    sh.do_destroy_rebuild_test_database(**LOUD)
    sh.setup_git_repo(**LOUD)

    with sh.sudo:
        sh.cp(os.path.join(ZULIP_PATH, "tools", "provision", "zulip-dev.conf"), "/etc/supervisor/conf.d/zulip-dev.conf", **LOUD)
        sh.service("supervisor", "restart", **LOUD)

if __name__ == "__main__":
    sys.exit(main())
