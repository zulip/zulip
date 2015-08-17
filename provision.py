import os

try:
    import sh
except ImportError:
    import pbs as sh

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
        "git",
    ]
}

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

# TODO: support other architectures
ARCH = "amd64"

VENV_PATH="/srv/zulip-venv"
ZULIP_PATH="/srv/zulip"

with sh.sudo:
    sh.apt_get.update()

    # TODO(lfaraone): add support for other distros
    sh.apt_get.install("-y", *APT_DEPENDENCIES["trusty"])

temp_deb_path = sh.mktemp("--tmpdir", "package_XXXXXX.deb")

sh.wget(
    "{}/{}_{}_{}.deb".format(
        TSEARCH_URL_BASE,
        TSEARCH_PACKAGE_NAME["trusty"],
        TSEARCH_VERSION,
        ARCH,
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

orig_path = os.environ["PATH"]
os.environ["PATH"] = os.pathsep.join((
        os.path.join(ZULIP_PATH, "tools"),
        os.path.join(ZULIP_PATH, "scripts", "setup"),
        orig_path
))

activate_this = os.path.join(VENV_PATH, "bin", "activate_this.py")
execfile(activate_this, dict(__file__=activate_this))

sh.pip.install(r="requirements.txt")
with sh.sudo:
    sh.cp(TSEARCH_STOPWORDS_PATH, REPO_STOPWORDS_PATH)

os.chdir(ZULIP_PATH)

import sys

sh.configure_rabbitmq()
sh.postgres_init_db()
sh.do_destroy_rebuild_database()
sh.postgres_init_test_db()
sh.do_destroy_rebuild_test_database()
