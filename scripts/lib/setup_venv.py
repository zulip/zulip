import os

from scripts.lib.zulip_tools import os_families

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VENV_DEPENDENCIES = [
    "build-essential",
    "libffi-dev",
    "libldap2-dev",
    "python3-dev",  # Needed to install typed-ast dependency of mypy
    "python3-pip",
    "virtualenv",
    "libxml2-dev",  # Used for installing talon-core and python-xmlsec
    "libxslt1-dev",  # Used for installing talon-core
    "libpq-dev",  # Needed by psycopg2
    "libssl-dev",  # Needed to build pycurl and other libraries
    "libmagic1",  # Used for install python-magic
    "libyaml-dev",  # For fast YAML parsing in PyYAML
    # Needed by python-xmlsec:
    "libxmlsec1-dev",
    "pkg-config",
    "jq",  # No longer used in production (clean me up later)
    "libsasl2-dev",  # For building python-ldap from source
    "libvips",  # For thumbnailing
    "libvips-tools",
]

COMMON_YUM_VENV_DEPENDENCIES = [
    "libffi-devel",
    "openldap-devel",
    "libyaml-devel",
    # Needed by python-xmlsec:
    "gcc",
    "python3-devel",
    "libxml2-devel",
    "xmlsec1-devel",
    "xmlsec1-openssl-devel",
    "libtool-ltdl-devel",
    "libxslt-devel",
    "postgresql-libs",  # libpq-dev on apt
    "openssl-devel",
    "jq",
    "vips",  # For thumbnailing
    "vips-tools",
]

REDHAT_VENV_DEPENDENCIES = [
    *COMMON_YUM_VENV_DEPENDENCIES,
    "python36-devel",
    "python-virtualenv",
]

FEDORA_VENV_DEPENDENCIES = [
    *COMMON_YUM_VENV_DEPENDENCIES,
    "python3-pip",
    "virtualenv",  # see https://unix.stackexchange.com/questions/27877/install-virtualenv-on-fedora-16
]


def get_venv_dependencies(vendor: str, os_version: str) -> list[str]:
    if "debian" in os_families():
        return VENV_DEPENDENCIES
    elif "rhel" in os_families():
        return REDHAT_VENV_DEPENDENCIES
    elif "fedora" in os_families():
        return FEDORA_VENV_DEPENDENCIES
    else:
        raise AssertionError("Invalid vendor")
