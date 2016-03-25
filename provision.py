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
    ],
}

VENV_PATH="/srv/zulip-venv"
ZULIP_PATH="/srv/zulip"

if not os.path.exists(os.path.join(os.path.dirname(__file__), ".git")):
    print("Error: No Zulip git repository present at /srv/zulip!")
    print("To setup the Zulip development environment, you should clone the code")
    print("from GitHub, rather than using a Zulip production release tarball.")
    sys.exit(1)

# TODO: Parse arguments properly
if "--travis" in sys.argv or "--docker" in sys.argv:
    ZULIP_PATH="."

# tsearch-extras is an extension to postgres's built-in full-text search.
# TODO: use a real APT repository
TSEARCH_URL_BASE = "https://dl.dropboxusercontent.com/u/283158365/zuliposs/"
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

NO_SYM_LINK = "--no-bin-links"


def main():
    log = logging.getLogger("zulip-provisioner")

    if platform.architecture()[0] == '64bit':
        arch = 'amd64'
        phantomjs_arch = 'x86_64'
    elif platform.architecture()[0] == '32bit':
        arch = "i386"
        phantomjs_arch = 'i686'
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
        PHANTOMJS_BASENAME = "phantomjs-1.9.8-linux-%s" % (phantomjs_arch,)
        PHANTOMJS_TARBALL_BASENAME = PHANTOMJS_BASENAME + ".tar.bz2"
        PHANTOMJS_TARBALL = os.path.join(PHANTOMJS_PATH, PHANTOMJS_TARBALL_BASENAME)
        PHANTOMJS_URL = "https://bitbucket.org/ariya/phantomjs/downloads/%s" % (PHANTOMJS_TARBALL_BASENAME,)
        sh.mkdir("-p", PHANTOMJS_PATH, **LOUD)
        if not os.path.exists(PHANTOMJS_TARBALL):
            sh.wget(PHANTOMJS_URL, output_document=PHANTOMJS_TARBALL, **LOUD)
        try:
             sh.tar("xj", directory=PHANTOMJS_PATH, file=PHANTOMJS_TARBALL, **LOUD)
        except Error:
            sh.tar("xz", directory=PHATOMJS_PATH, file=PHANTOMJS_TARBALL, **LOUD)
        sh.ln("-sf", os.path.join(PHANTOMJS_PATH, PHANTOMJS_BASENAME, "bin", "phantomjs"),
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

    # npm install and management commands expect to be run from the root of the project.
    os.chdir(ZULIP_PATH)

    if os.name != "nt":
        sh.npm.install(**LOUD)
    else:
        sh.npm.install(NO_SYM_LINK, **LOUD)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
