import os
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
    sh.apt_get.update()

    sh.apt_get.install(*APT_DEPENDENCIES["trusty"], assume_yes=True)

temp_deb_path = sh.mktemp("package_XXXXXX.deb", tmpdir=True)

sh.wget(
    "{}/{}_{}_{}.deb".format(
        TSEARCH_URL_BASE,
        TSEARCH_PACKAGE_NAME["trusty"],
        TSEARCH_VERSION,
        arch,
    ),
    output_document=temp_deb_path,
)

with sh.sudo:
    sh.dpkg("--install", temp_deb_path)

with sh.sudo:
    sh.rm("-rf", VENV_PATH)
    sh.mkdir("-p", VENV_PATH)
    sh.chown("{}:{}".format(os.getuid(), os.getgid()), VENV_PATH)

sh.virtualenv(VENV_PATH)

# Add the ./tools and ./scripts/setup directories inside the repository root to
# the system path; we'll reference them later.
orig_path = os.environ["PATH"]
os.environ["PATH"] = os.pathsep.join((
        os.path.join(ZULIP_PATH, "tools"),
        os.path.join(ZULIP_PATH, "scripts", "setup"),
        orig_path
))

# Switch current Python context to the virtualenv.
activate_this = os.path.join(VENV_PATH, "bin", "activate_this.py")
execfile(activate_this, dict(__file__=activate_this))

sh.pip.install(requirement=os.path.join(ZULIP_PATH, "requirements.txt"))
with sh.sudo:
    sh.cp(REPO_STOPWORDS_PATH, TSEARCH_STOPWORDS_PATH)

# Management commands expect to be run from the root of the project.
os.chdir(ZULIP_PATH)

os.system("generate_enterprise_secrets.py -d")
sh.configure_rabbitmq()
sh.postgres_init_db()
sh.do_destroy_rebuild_database()
sh.postgres_init_test_db()
sh.do_destroy_rebuild_test_database()
sh.setup_git_repo()

with sh.sudo:
    sh.cp(os.path.join(ZULIP_PATH, "tools", "provision", "zulip-dev.conf"), "/etc/supervisor/conf.d/zulip-dev.conf")
    sh.service("supervisor", "restart")
