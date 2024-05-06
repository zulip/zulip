import logging
import os
import sys
import time
from copy import deepcopy
from typing import Any, Dict, Final, List, Literal, Tuple, Union
from urllib.parse import urljoin

from scripts.lib.zulip_tools import get_tornado_ports
from zerver.lib.db import TimeTrackingConnection, TimeTrackingCursor

from .config import (
    DEPLOY_ROOT,
    config_file,
    get_config,
    get_from_file_if_exists,
    get_mandatory_secret,
    get_secret,
)
from .config import DEVELOPMENT as DEVELOPMENT
from .config import PRODUCTION as PRODUCTION
from .configured_settings import (
    ADMINS,
    ALLOWED_HOSTS,
    AUTH_LDAP_BIND_DN,
    AUTH_LDAP_CONNECTION_OPTIONS,
    AUTH_LDAP_SERVER_URI,
    AUTHENTICATION_BACKENDS,
    CAMO_URI,
    CUSTOM_HOME_NOT_LOGGED_IN,
    DEBUG,
    DEBUG_ERROR_REPORTING,
    DEFAULT_RATE_LIMITING_RULES,
    EMAIL_BACKEND,
    EMAIL_HOST,
    ERROR_REPORTING,
    EXTERNAL_HOST,
    EXTERNAL_HOST_WITHOUT_PORT,
    EXTERNAL_URI_SCHEME,
    EXTRA_INSTALLED_APPS,
    GOOGLE_OAUTH2_CLIENT_ID,
    IS_DEV_DROPLET,
    LOCAL_UPLOADS_DIR,
    MEMCACHED_LOCATION,
    MEMCACHED_USERNAME,
    RATE_LIMITING_RULES,
    REALM_HOSTS,
    REGISTER_LINK_DISABLED,
    REMOTE_POSTGRES_HOST,
    REMOTE_POSTGRES_PORT,
    REMOTE_POSTGRES_SSLMODE,
    ROOT_SUBDOMAIN_ALIASES,
    SENTRY_DSN,
    SOCIAL_AUTH_APPLE_APP_ID,
    SOCIAL_AUTH_APPLE_SERVICES_ID,
    SOCIAL_AUTH_GITHUB_KEY,
    SOCIAL_AUTH_GITHUB_ORG_NAME,
    SOCIAL_AUTH_GITHUB_TEAM_ID,
    SOCIAL_AUTH_GOOGLE_KEY,
    SOCIAL_AUTH_SAML_ENABLED_IDPS,
    SOCIAL_AUTH_SAML_SECURITY_CONFIG,
    SOCIAL_AUTH_SUBDOMAIN,
    STATIC_URL,
    TORNADO_PORTS,
    USING_PGROONGA,
    ZULIP_ADMINISTRATOR,
)

########################################################################
# INITIAL SETTINGS
########################################################################

# Make this unique, and don't share it with anybody.
SECRET_KEY = get_mandatory_secret("secret_key")

# A shared secret, used to authenticate different parts of the app to each other.
SHARED_SECRET = get_mandatory_secret("shared_secret")

# We use this salt to hash a user's email into a filename for their user-uploaded
# avatar.  If this salt is discovered, attackers will only be able to determine
# that the owner of an email account has uploaded an avatar to Zulip, which isn't
# the end of the world.  Don't use the salt where there is more security exposure.
AVATAR_SALT = get_mandatory_secret("avatar_salt")

# SERVER_GENERATION is used to track whether the server has been
# restarted for triggering browser clients to reload.
SERVER_GENERATION = int(time.time())

# Key to authenticate this server to zulip.org for push notifications, etc.
ZULIP_ORG_KEY = get_secret("zulip_org_key")
ZULIP_ORG_ID = get_secret("zulip_org_id")

if DEBUG:
    INTERNAL_IPS = ("127.0.0.1",)

# Detect whether we're running as a queue worker; this impacts the logging configuration.
if len(sys.argv) > 2 and sys.argv[0].endswith("manage.py") and sys.argv[1] == "process_queue":
    IS_WORKER = True
else:
    IS_WORKER = False


# This is overridden in test_settings.py for the test suites
PUPPETEER_TESTS = False
# This is overridden in test_settings.py for the test suites
RUNNING_OPENAPI_CURL_TEST = False
# This is overridden in test_settings.py for the test suites
GENERATE_STRIPE_FIXTURES = False
# This is overridden in test_settings.py for the test suites
BAN_CONSOLE_OUTPUT = False
# This is overridden in test_settings.py for the test suites
TEST_WORKER_DIR = ""

# These are the settings that we will check that the user has filled in for
# production deployments before starting the app.  It consists of a series
# of pairs of (setting name, default value that it must be changed from)
REQUIRED_SETTINGS = [
    ("EXTERNAL_HOST", "zulip.example.com"),
    ("ZULIP_ADMINISTRATOR", "zulip-admin@example.com"),
    # SECRET_KEY doesn't really need to be here, in
    # that we set it automatically, but just in
    # case, it seems worth having in this list
    ("SECRET_KEY", ""),
    ("AUTHENTICATION_BACKENDS", ()),
]

MANAGERS = ADMINS

########################################################################
# STANDARD DJANGO SETTINGS
########################################################################

# Local time zone for this installation. Choices can be found here:
# https://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = "UTC"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# this directory will be used to store logs for development environment
DEVELOPMENT_LOG_DIRECTORY = os.path.join(DEPLOY_ROOT, "var", "log")

# Extend ALLOWED_HOSTS with localhost (needed to RPC to Tornado),
ALLOWED_HOSTS += ["127.0.0.1", "localhost"]
# ... with hosts corresponding to EXTERNAL_HOST,
ALLOWED_HOSTS += [EXTERNAL_HOST_WITHOUT_PORT, "." + EXTERNAL_HOST_WITHOUT_PORT]
# ... and with the hosts in REALM_HOSTS.
ALLOWED_HOSTS += REALM_HOSTS.values()

MIDDLEWARE = [
    "zerver.middleware.TagRequests",
    "zerver.middleware.SetRemoteAddrFromRealIpHeader",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Important: All middleware before LogRequests should be
    # inexpensive, because any time spent in that middleware will not
    # be counted in the LogRequests instrumentation of how time was
    # spent while processing a request.
    "zerver.middleware.LogRequests",
    "zerver.middleware.JsonErrorHandler",
    "zerver.middleware.RateLimitMiddleware",
    "zerver.middleware.FlushDisplayRecipientCache",
    "django.middleware.common.CommonMiddleware",
    "zerver.middleware.LocaleMiddleware",
    "zerver.middleware.HostDomainMiddleware",
    "zerver.middleware.DetectProxyMisconfiguration",
    "django.middleware.csrf.CsrfViewMiddleware",
    # Make sure 2FA middlewares come after authentication middleware.
    "django_otp.middleware.OTPMiddleware",  # Required by two factor auth.
    "two_factor.middleware.threadlocals.ThreadLocals",  # Required by Twilio
]

AUTH_USER_MODEL = "zerver.UserProfile"

TEST_RUNNER = "zerver.lib.test_runner.Runner"

ROOT_URLCONF = "zproject.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "zproject.wsgi.application"

# A site can include additional installed apps via the
# EXTRA_INSTALLED_APPS setting
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "confirmation",
    "zerver",
    "social_django",
    "django_scim",
    # 2FA related apps.
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "two_factor",
    "two_factor.plugins.phonenumber",
]
if USING_PGROONGA:
    INSTALLED_APPS += ["pgroonga"]
INSTALLED_APPS += EXTRA_INSTALLED_APPS

ZILENCER_ENABLED = "zilencer" in INSTALLED_APPS
CORPORATE_ENABLED = "corporate" in INSTALLED_APPS

if not TORNADO_PORTS:
    TORNADO_PORTS = get_tornado_ports(config_file)
TORNADO_PROCESSES = len(TORNADO_PORTS)

RUNNING_INSIDE_TORNADO = False

SILENCED_SYSTEM_CHECKS = [
    # auth.W004 checks that the UserProfile field named by USERNAME_FIELD has
    # `unique=True`.  For us this is `email`, and it's unique only per-realm.
    # Per Django docs, this is perfectly fine so long as our authentication
    # backends support the username not being unique; and they do.
    # See: https://docs.djangoproject.com/en/3.2/topics/auth/customizing/#django.contrib.auth.models.CustomUser.USERNAME_FIELD
    "auth.W004",
    # models.E034 limits index names to 30 characters for Oracle compatibility.
    # We aren't using Oracle.
    "models.E034",
]

########################################################################
# DATABASE CONFIGURATION
########################################################################

# Zulip's Django configuration supports 4 different ways to do
# PostgreSQL authentication:
#
# * The development environment uses the `local_database_password`
#   secret from `zulip-secrets.conf` to authenticate with a local
#   database.  The password is automatically generated and managed by
#   `generate_secrets.py` during or provision.
#
# The remaining 3 options are for production use:
#
# * Using PostgreSQL's "peer" authentication to authenticate to a
#   database on the local system using one's user ID (processes
#   running as user `zulip` on the system are automatically
#   authenticated as database user `zulip`).  This is the default in
#   production.  We don't use this in the development environment,
#   because it requires the developer's user to be called `zulip`.
#
# * Using password authentication with a remote PostgreSQL server using
#   the `REMOTE_POSTGRES_HOST` setting and the password from the
#   `postgres_password` secret.
#
# * Using passwordless authentication with a remote PostgreSQL server
#   using the `REMOTE_POSTGRES_HOST` setting and a client certificate
#   under `/home/zulip/.postgresql/`.
#
# We implement these options with a default DATABASES configuration
# supporting peer authentication, with logic to override it as
# appropriate if DEVELOPMENT or REMOTE_POSTGRES_HOST is set.
DATABASES: Dict[str, Dict[str, Any]] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_config("postgresql", "database_name", "zulip"),
        "USER": get_config("postgresql", "database_user", "zulip"),
        # Password = '' => peer/certificate authentication (no password)
        "PASSWORD": "",
        # Host = '' => connect to localhost by default
        "HOST": "",
        "SCHEMA": "zulip",
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connection_factory": TimeTrackingConnection,
            "cursor_factory": TimeTrackingCursor,
            # The default is null, which means no timeout; 2 is the
            # minimum allowed value.  We set this low, so we move on
            # quickly, in the case that the server is running but
            # unable to handle new connections for some reason.
            "connect_timeout": 2,
        },
    }
}

if DEVELOPMENT:
    LOCAL_DATABASE_PASSWORD = get_secret("local_database_password")
    DATABASES["default"].update(
        PASSWORD=LOCAL_DATABASE_PASSWORD,
        HOST="localhost",
    )
elif REMOTE_POSTGRES_HOST != "":
    DATABASES["default"].update(
        HOST=REMOTE_POSTGRES_HOST,
        PORT=REMOTE_POSTGRES_PORT,
    )
    if "," in REMOTE_POSTGRES_HOST:
        DATABASES["default"]["OPTIONS"]["target_session_attrs"] = "read-write"
    if get_secret("postgres_password") is not None:
        DATABASES["default"].update(
            PASSWORD=get_secret("postgres_password"),
        )
    if REMOTE_POSTGRES_SSLMODE != "":
        DATABASES["default"]["OPTIONS"]["sslmode"] = REMOTE_POSTGRES_SSLMODE
    else:
        DATABASES["default"]["OPTIONS"]["sslmode"] = "verify-full"
elif (
    get_config("postgresql", "database_user", "zulip") != "zulip"
    and get_secret("postgres_password") is not None
):
    DATABASES["default"].update(
        PASSWORD=get_secret("postgres_password"),
        HOST="localhost",
    )
POSTGRESQL_MISSING_DICTIONARIES = get_config("postgresql", "missing_dictionaries", False)

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

########################################################################
# RABBITMQ CONFIGURATION
########################################################################

USING_RABBITMQ = True
RABBITMQ_PASSWORD = get_secret("rabbitmq_password")

########################################################################
# CACHING CONFIGURATION
########################################################################

SESSION_ENGINE = "zerver.lib.safe_session_cached_db"

MEMCACHED_PASSWORD = get_secret("memcached_password")

CACHES: Dict[str, Dict[str, object]] = {
    "default": {
        "BACKEND": "zerver.lib.singleton_bmemcached.SingletonBMemcached",
        "LOCATION": MEMCACHED_LOCATION,
        "OPTIONS": {
            "socket_timeout": 3600,
            "username": MEMCACHED_USERNAME,
            "password": MEMCACHED_PASSWORD,
            "pickle_protocol": 4,
        },
    },
    "database": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "third_party_api_results",
        # This cache shouldn't timeout; we're really just using the
        # cache API to store the results of requests to third-party
        # APIs like the Twitter API permanently.
        "TIMEOUT": None,
        "OPTIONS": {
            "MAX_ENTRIES": 100000000,
            "CULL_FREQUENCY": 10,
        },
    },
}

########################################################################
# REDIS-BASED RATE LIMITING CONFIGURATION
########################################################################

# Merge any local overrides with the default rules.
RATE_LIMITING_RULES = {**DEFAULT_RATE_LIMITING_RULES, **RATE_LIMITING_RULES}

# List of domains that, when applied to a request in a Tornado process,
# will be handled with the separate in-memory rate limiting backend for Tornado,
# which has its own buckets separate from the default backend.
# In principle, it should be impossible to make requests to tornado that fall into
# other domains, but we use this list as an extra precaution.
RATE_LIMITING_DOMAINS_FOR_TORNADO = ["api_by_user", "api_by_ip"]

# These ratelimits are also documented publicly at
# https://zulip.readthedocs.io/en/latest/production/email-gateway.html
RATE_LIMITING_MIRROR_REALM_RULES = [
    (60, 50),  # 50 emails per minute
    (300, 120),  # 120 emails per 5 minutes
    (3600, 600),  # 600 emails per hour
]

DEBUG_RATE_LIMITING = DEBUG
REDIS_PASSWORD = get_secret("redis_password")

# See RATE_LIMIT_TOR_TOGETHER
if DEVELOPMENT:
    TOR_EXIT_NODE_FILE_PATH = os.path.join(DEPLOY_ROOT, "var/tor-exit-nodes.json")
else:
    TOR_EXIT_NODE_FILE_PATH = "/var/lib/zulip/tor-exit-nodes.json"

########################################################################
# SECURITY SETTINGS
########################################################################

# Tell the browser to never send our cookies without encryption, e.g.
# when executing the initial http -> https redirect.
#
# Turn it off for local testing because we don't have SSL.
if PRODUCTION:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    LANGUAGE_COOKIE_SECURE = True

    # https://tools.ietf.org/html/draft-ietf-httpbis-rfc6265bis-05#section-4.1.3.2
    SESSION_COOKIE_NAME = "__Host-sessionid"
    CSRF_COOKIE_NAME = "__Host-csrftoken"

# Prevent JavaScript from reading the CSRF token from cookies.  Our code gets
# the token from the DOM, which means malicious code could too.  But hiding the
# cookie will slow down some attackers.
CSRF_COOKIE_HTTPONLY = True
CSRF_FAILURE_VIEW = "zerver.middleware.csrf_failure"

# Avoid a deprecation message in the Firefox console
LANGUAGE_COOKIE_SAMESITE: Final = "Lax"

if DEVELOPMENT:
    # Use fast password hashing for creating testing users when not
    # PRODUCTION.  Saves a bunch of time.
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
        "django.contrib.auth.hashers.SHA1PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
    # Also we auto-generate passwords for the default users which you
    # can query using ./manage.py print_initial_password
    INITIAL_PASSWORD_SALT = get_secret("initial_password_salt")
else:
    # For production, use the best password hashing algorithm: Argon2
    # Zulip was originally on PBKDF2 so we need it for compatibility
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.Argon2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]

########################################################################
# API/BOT SETTINGS
########################################################################

ROOT_DOMAIN_URI = EXTERNAL_URI_SCHEME + EXTERNAL_HOST

S3_KEY = get_secret("s3_key")
S3_SECRET_KEY = get_secret("s3_secret_key")

# GCM tokens are IP-whitelisted; if we deploy to additional
# servers you will need to explicitly add their IPs here:
# https://cloud.google.com/console/project/apps~zulip-android/apiui/credential
ANDROID_GCM_API_KEY = get_secret("android_gcm_api_key")

DROPBOX_APP_KEY = get_secret("dropbox_app_key")

BIG_BLUE_BUTTON_SECRET = get_secret("big_blue_button_secret")

# Twitter API credentials
# Secrecy not required because its only used for R/O requests.
# Please don't make us go over our rate limit.
TWITTER_CONSUMER_KEY = get_secret("twitter_consumer_key")
TWITTER_CONSUMER_SECRET = get_secret("twitter_consumer_secret")
TWITTER_ACCESS_TOKEN_KEY = get_secret("twitter_access_token_key")
TWITTER_ACCESS_TOKEN_SECRET = get_secret("twitter_access_token_secret")

# These are the bots that Zulip sends automated messages as.
INTERNAL_BOTS = [
    {
        "var_name": "NOTIFICATION_BOT",
        "email_template": "notification-bot@%s",
        "name": "Notification Bot",
    },
    {
        "var_name": "EMAIL_GATEWAY_BOT",
        "email_template": "emailgateway@%s",
        "name": "Email Gateway",
    },
    {
        "var_name": "NAGIOS_SEND_BOT",
        "email_template": "nagios-send-bot@%s",
        "name": "Nagios Send Bot",
    },
    {
        "var_name": "NAGIOS_RECEIVE_BOT",
        "email_template": "nagios-receive-bot@%s",
        "name": "Nagios Receive Bot",
    },
    {
        "var_name": "WELCOME_BOT",
        "email_template": "welcome-bot@%s",
        "name": "Welcome Bot",
    },
]

# Bots that are created for each realm like the reminder-bot goes here.
REALM_INTERNAL_BOTS: List[Dict[str, str]] = []
# These are realm-internal bots that may exist in some organizations,
# so configure power the setting, but should not be auto-created at this time.
DISABLED_REALM_INTERNAL_BOTS = [
    {
        "var_name": "REMINDER_BOT",
        "email_template": "reminder-bot@%s",
        "name": "Reminder Bot",
    },
]

if PRODUCTION:
    INTERNAL_BOTS += [
        {
            "var_name": "NAGIOS_STAGING_SEND_BOT",
            "email_template": "nagios-staging-send-bot@%s",
            "name": "Nagios Staging Send Bot",
        },
        {
            "var_name": "NAGIOS_STAGING_RECEIVE_BOT",
            "email_template": "nagios-staging-receive-bot@%s",
            "name": "Nagios Staging Receive Bot",
        },
    ]

INTERNAL_BOT_DOMAIN = "zulip.com"

########################################################################
# CAMO HTTPS CACHE CONFIGURATION
########################################################################

# This needs to be synced with the Camo installation
CAMO_KEY = get_secret("camo_key") if CAMO_URI != "" else None

########################################################################
# KATEX SERVER SETTINGS
########################################################################

KATEX_SERVER = get_config("application_server", "katex_server", False)
KATEX_SERVER_PORT = get_config("application_server", "katex_server_port", "9700")


########################################################################
# STATIC CONTENT AND MINIFICATION SETTINGS
########################################################################

if STATIC_URL is None:
    if PRODUCTION or IS_DEV_DROPLET or os.getenv("EXTERNAL_HOST") is not None:
        STATIC_URL = urljoin(ROOT_DOMAIN_URI, "/static/")
    else:
        STATIC_URL = "http://localhost:9991/static/"

LOCAL_AVATARS_DIR = os.path.join(LOCAL_UPLOADS_DIR, "avatars") if LOCAL_UPLOADS_DIR else None
LOCAL_FILES_DIR = os.path.join(LOCAL_UPLOADS_DIR, "files") if LOCAL_UPLOADS_DIR else None

# ZulipStorage is a modified version of ManifestStaticFilesStorage,
# and, like that class, it inserts a file hash into filenames
# to prevent the browser from using stale files from cache.
#
# Unlike PipelineStorage, it requires the files to exist in
# STATIC_ROOT even for dev servers.  So we only use
# ZulipStorage when not DEBUG.

if not DEBUG:
    STATICFILES_STORAGE = "zerver.lib.storage.ZulipStorage"
    if PRODUCTION:
        STATIC_ROOT = "/home/zulip/prod-static"
    else:
        STATIC_ROOT = os.path.abspath(os.path.join(DEPLOY_ROOT, "prod-static/serve"))

# If changing this, you need to also the hack modifications to this in
# our compilemessages management command.
LOCALE_PATHS = (os.path.join(DEPLOY_ROOT, "locale"),)

# We want all temporary uploaded files to be stored on disk.
FILE_UPLOAD_MAX_MEMORY_SIZE = 0

if DEVELOPMENT or "ZULIP_COLLECTING_STATIC" in os.environ:
    STATICFILES_DIRS = [os.path.join(DEPLOY_ROOT, "static")]

if DEBUG:
    WEBPACK_BUNDLES = "../webpack/"
    WEBPACK_STATS_FILE = os.path.join(DEPLOY_ROOT, "var", "webpack-stats-dev.json")
else:
    WEBPACK_BUNDLES = "webpack-bundles/"
    WEBPACK_STATS_FILE = os.path.join(DEPLOY_ROOT, "webpack-stats-production.json")

########################################################################
# TEMPLATES SETTINGS
########################################################################

# List of callables that know how to import templates from various sources.
LOADERS: List[Union[str, Tuple[object, ...]]] = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]
if PRODUCTION:
    # Template caching is a significant performance win in production.
    LOADERS = [("django.template.loaders.cached.Loader", LOADERS)]

base_template_engine_settings: Dict[str, Any] = {
    "BACKEND": "django.template.backends.jinja2.Jinja2",
    "OPTIONS": {
        "environment": "zproject.jinja2.environment",
        "extensions": [
            "jinja2.ext.i18n",
        ],
        "context_processors": [
            "zerver.context_processors.zulip_default_context",
            "django.template.context_processors.i18n",
        ],
    },
}

if CORPORATE_ENABLED:
    base_template_engine_settings["OPTIONS"]["context_processors"].append(
        "zerver.context_processors.zulip_default_corporate_context"
    )

default_template_engine_settings = deepcopy(base_template_engine_settings)
default_template_engine_settings.update(
    NAME="Jinja2",
    DIRS=[
        # The main templates directory
        os.path.join(DEPLOY_ROOT, "templates"),
        # The webhook integration templates
        os.path.join(DEPLOY_ROOT, "zerver", "webhooks"),
        # The python-zulip-api:zulip_bots package templates
        os.path.join("static" if DEBUG else STATIC_ROOT, "generated", "bots"),
    ],
    APP_DIRS=True,
)

non_html_template_engine_settings = deepcopy(base_template_engine_settings)
non_html_template_engine_settings.update(
    NAME="Jinja2_plaintext",
    DIRS=[os.path.join(DEPLOY_ROOT, "templates")],
    APP_DIRS=False,
)
non_html_template_engine_settings["OPTIONS"].update(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

# django-two-factor uses the default Django template engine (not Jinja2), so we
# need to add config for it here.
two_factor_template_options = deepcopy(default_template_engine_settings["OPTIONS"])
del two_factor_template_options["environment"]
del two_factor_template_options["extensions"]
two_factor_template_options["loaders"] = ["zproject.template_loaders.TwoFactorLoader"]

two_factor_template_engine_settings = {
    "NAME": "Two_Factor",
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": False,
    "OPTIONS": two_factor_template_options,
}

# The order here is important; get_template and related/parent functions try
# the template engines in order until one succeeds.
TEMPLATES = [
    default_template_engine_settings,
    non_html_template_engine_settings,
    two_factor_template_engine_settings,
]
########################################################################
# LOGGING SETTINGS
########################################################################


def zulip_path(path: str) -> str:
    if DEVELOPMENT:
        # if DEVELOPMENT, store these files in the Zulip checkout
        if path.startswith("/var/log"):
            path = os.path.join(DEVELOPMENT_LOG_DIRECTORY, os.path.basename(path))
        else:
            path = os.path.join(os.path.join(DEPLOY_ROOT, "var"), os.path.basename(path))
    return path


SERVER_LOG_PATH = zulip_path("/var/log/zulip/server.log")
ERROR_FILE_LOG_PATH = zulip_path("/var/log/zulip/errors.log")
MANAGEMENT_LOG_PATH = zulip_path("/var/log/zulip/manage.log")
WORKER_LOG_PATH = zulip_path("/var/log/zulip/workers.log")
SLOW_QUERIES_LOG_PATH = zulip_path("/var/log/zulip/slow_queries.log")
JSON_PERSISTENT_QUEUE_FILENAME_PATTERN = zulip_path("/home/zulip/tornado/event_queues%s.json")
EMAIL_LOG_PATH = zulip_path("/var/log/zulip/send_email.log")
EMAIL_MIRROR_LOG_PATH = zulip_path("/var/log/zulip/email_mirror.log")
EMAIL_DELIVERER_LOG_PATH = zulip_path("/var/log/zulip/email_deliverer.log")
EMAIL_CONTENT_LOG_PATH = zulip_path("/var/log/zulip/email_content.log")
LDAP_LOG_PATH = zulip_path("/var/log/zulip/ldap.log")
LDAP_SYNC_LOG_PATH = zulip_path("/var/log/zulip/sync_ldap_user_data.log")
QUEUE_ERROR_DIR = zulip_path("/var/log/zulip/queue_error")
QUEUE_STATS_DIR = zulip_path("/var/log/zulip/queue_stats")
DIGEST_LOG_PATH = zulip_path("/var/log/zulip/digest.log")
ANALYTICS_LOG_PATH = zulip_path("/var/log/zulip/analytics.log")
WEBHOOK_LOG_PATH = zulip_path("/var/log/zulip/webhooks_errors.log")
WEBHOOK_ANOMALOUS_PAYLOADS_LOG_PATH = zulip_path("/var/log/zulip/webhooks_anomalous_payloads.log")
WEBHOOK_UNSUPPORTED_EVENTS_LOG_PATH = zulip_path("/var/log/zulip/webhooks_unsupported_events.log")
SOFT_DEACTIVATION_LOG_PATH = zulip_path("/var/log/zulip/soft_deactivation.log")
TRACEMALLOC_DUMP_DIR = zulip_path("/var/log/zulip/tracemalloc")
DELIVER_SCHEDULED_MESSAGES_LOG_PATH = zulip_path("/var/log/zulip/deliver_scheduled_messages.log")
RETENTION_LOG_PATH = zulip_path("/var/log/zulip/message_retention.log")
AUTH_LOG_PATH = zulip_path("/var/log/zulip/auth.log")
SCIM_LOG_PATH = zulip_path("/var/log/zulip/scim.log")

ZULIP_WORKER_TEST_FILE = zulip_path("/var/log/zulip/zulip-worker-test-file")

LOCKFILE_DIRECTORY = (
    "/srv/zulip-locks" if not DEVELOPMENT else os.path.join(os.path.join(DEPLOY_ROOT, "var/locks"))
)


if IS_WORKER:
    FILE_LOG_PATH = WORKER_LOG_PATH
else:
    FILE_LOG_PATH = SERVER_LOG_PATH

DEFAULT_ZULIP_HANDLERS = [
    *(["mail_admins"] if ERROR_REPORTING else []),
    "console",
    "file",
    "errors_file",
]


def skip_200_and_304(record: logging.LogRecord) -> bool:
    # Apparently, `status_code` is added by Django and is not an actual
    # attribute of LogRecord; as a result, mypy throws an error if we
    # access the `status_code` attribute directly.
    return getattr(record, "status_code", None) not in [200, 304]


def skip_site_packages_logs(record: logging.LogRecord) -> bool:
    # This skips the log records that are generated from libraries
    # installed in site packages.
    # Workaround for https://code.djangoproject.com/ticket/26886
    return "site-packages" not in record.pathname


def file_handler(
    filename: str,
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG",
    formatter: str = "default",
) -> Dict[str, str]:
    return {
        "filename": filename,
        "level": level,
        "formatter": formatter,
        "class": "logging.handlers.WatchedFileHandler",
    }


LOGGING: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "zerver.lib.logging_util.ZulipFormatter",
        },
        "webhook_request_data": {
            "()": "zerver.lib.logging_util.ZulipWebhookFormatter",
        },
    },
    "filters": {
        "ZulipLimiter": {
            "()": "zerver.lib.logging_util.ZulipLimiter",
        },
        "EmailLimiter": {
            "()": "zerver.lib.logging_util.EmailLimiter",
        },
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "nop": {
            "()": "zerver.lib.logging_util.ReturnTrue",
        },
        "require_really_deployed": {
            "()": "zerver.lib.logging_util.RequireReallyDeployed",
        },
        "skip_200_and_304": {
            "()": "django.utils.log.CallbackFilter",
            "callback": skip_200_and_304,
        },
        "skip_site_packages_logs": {
            "()": "django.utils.log.CallbackFilter",
            "callback": skip_site_packages_logs,
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": (
                ["ZulipLimiter", "require_debug_false", "require_really_deployed"]
                if not DEBUG_ERROR_REPORTING
                else []
            ),
        },
        "analytics_file": file_handler(ANALYTICS_LOG_PATH),
        "auth_file": file_handler(AUTH_LOG_PATH),
        "errors_file": file_handler(ERROR_FILE_LOG_PATH, level="WARNING"),
        "file": file_handler(FILE_LOG_PATH),
        "ldap_file": file_handler(LDAP_LOG_PATH),
        "scim_file": file_handler(SCIM_LOG_PATH),
        "slow_queries_file": file_handler(SLOW_QUERIES_LOG_PATH, level="INFO"),
        "webhook_anomalous_file": file_handler(
            WEBHOOK_ANOMALOUS_PAYLOADS_LOG_PATH, formatter="webhook_request_data"
        ),
        "webhook_file": file_handler(WEBHOOK_LOG_PATH, formatter="webhook_request_data"),
        "webhook_unsupported_file": file_handler(
            WEBHOOK_UNSUPPORTED_EVENTS_LOG_PATH, formatter="webhook_request_data"
        ),
    },
    "loggers": {
        # The Python logging module uses a hierarchy of logger names for config:
        # "foo.bar" has parent "foo" has parent "", the root.  But the semantics
        # are subtle: it walks this hierarchy once to find the log level to
        # decide whether to log the record at all, then a separate time to find
        # handlers to emit the record.
        #
        # For `level`, the most specific ancestor that has a `level` counts.
        # For `handlers`, the most specific ancestor that has a `handlers`
        # counts (assuming we set `propagate=False`, which we always do.)
        # These are independent -- they might come at the same layer, or
        # either one could come before the other.
        #
        # For `filters`, no ancestors count at all -- only the exact logger name
        # the record was logged at.
        #
        # Upstream docs: https://docs.python.org/3/library/logging
        #
        # Style rules:
        #  * Always set `propagate=False` if setting `handlers`.
        #  * Setting `level` equal to the parent is redundant; don't.
        #  * Setting `handlers` equal to the parent is redundant; don't.
        #  * Always write in order: level, filters, handlers, propagate.
        # root logger
        "": {
            "level": "INFO",
            "handlers": DEFAULT_ZULIP_HANDLERS,
        },
        # Django, alphabetized
        "django": {
            # Django's default logging config has already set some
            # things on this logger.  Just mentioning it here causes
            # `logging.config` to reset it to defaults, as if never
            # configured; which is what we want for it.
        },
        "django.request": {
            # We set this to ERROR to prevent Django's default
            # low-value logs with lines like "Not Found: /robots.txt"
            # from being logged for every HTTP 4xx error at WARNING
            # level, which would otherwise end up spamming our
            # errors.log.  We'll still get logs in errors.log
            # including tracebacks for 5xx errors (i.e. Python
            # exceptions).
            "level": "ERROR",
        },
        "django.security.DisallowedHost": {
            "handlers": ["file"],
            "propagate": False,
        },
        "django.server": {
            "filters": ["skip_200_and_304"],
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "django.utils.autoreload": {
            # We don't want logging spam from the autoreloaders in development.
            "level": "WARNING",
        },
        "django.template": {
            "level": "DEBUG",
            "filters": ["require_debug_true", "skip_site_packages_logs"],
            "handlers": ["console"],
            "propagate": False,
        },
        ## Uncomment the following to get all database queries logged to the console
        # 'django.db': {
        #     'level': 'DEBUG',
        #     'handlers': ['console'],
        #     'propagate': False,
        # },
        # other libraries, alphabetized
        "django_auth_ldap": {
            "level": "DEBUG",
            "handlers": ["console", "ldap_file", "errors_file"],
            "propagate": False,
        },
        "django_scim": {
            "level": "DEBUG",
            "handlers": ["scim_file", "errors_file"],
            "propagate": False,
        },
        "pika": {
            # pika is super chatty on INFO.
            "level": "WARNING",
            # pika spews a lot of ERROR logs when a connection fails.
            # We reconnect automatically, so those should be treated as WARNING --
            # write to the log for use in debugging, but no error emails/Zulips.
            "handlers": ["console", "file", "errors_file"],
            "propagate": False,
        },
        "requests": {
            "level": "WARNING",
        },
        # our own loggers, alphabetized
        "zerver.lib.digest": {
            "level": "DEBUG",
        },
        "zerver.management.commands.deliver_scheduled_emails": {
            "level": "DEBUG",
        },
        "zerver.management.commands.enqueue_digest_emails": {
            "level": "DEBUG",
        },
        "zerver.management.commands.deliver_scheduled_messages": {
            "level": "DEBUG",
        },
        "zulip.analytics": {
            "handlers": ["analytics_file", "errors_file"],
            "propagate": False,
        },
        "zulip.auth": {
            "level": "DEBUG",
            "handlers": [*DEFAULT_ZULIP_HANDLERS, "auth_file"],
            "propagate": False,
        },
        "zulip.ldap": {
            "level": "DEBUG",
            "handlers": ["console", "ldap_file", "errors_file"],
            "propagate": False,
        },
        "zulip.management": {
            "handlers": ["file", "errors_file"],
            "propagate": False,
        },
        "zulip.queue": {
            "level": "WARNING",
        },
        "zulip.retention": {
            "handlers": ["file", "errors_file"],
            "propagate": False,
        },
        "zulip.slow_queries": {
            "level": "INFO",
            "handlers": ["slow_queries_file"],
            "propagate": False,
        },
        "zulip.soft_deactivation": {
            "handlers": ["file", "errors_file"],
            "propagate": False,
        },
        "zulip.zerver.webhooks": {
            "level": "DEBUG",
            "handlers": ["file", "errors_file", "webhook_file"],
            "propagate": False,
        },
        "zulip.zerver.webhooks.unsupported": {
            "level": "DEBUG",
            "handlers": ["webhook_unsupported_file"],
            "propagate": False,
        },
        "zulip.zerver.webhooks.anomalous": {
            "level": "DEBUG",
            "handlers": ["webhook_anomalous_file"],
            "propagate": False,
        },
    },
}

if DEVELOPMENT:
    CONTRIBUTOR_DATA_FILE_PATH = os.path.join(DEPLOY_ROOT, "var/github-contributors.json")
else:
    CONTRIBUTOR_DATA_FILE_PATH = "/var/lib/zulip/github-contributors.json"

LOGIN_REDIRECT_URL = "/"

# Client-side polling timeout for get_events, in seconds.
# We configure this here so that the client test suite can override it.
# We already kill the connection server-side with heartbeat events,
# but it's good to have a safety.  This value should be greater than
# (HEARTBEAT_MIN_FREQ_SECS + 10)
EVENT_QUEUE_LONGPOLL_TIMEOUT_SECONDS = 90

########################################################################
# SSO AND LDAP SETTINGS
########################################################################

USING_LDAP = "zproject.backends.ZulipLDAPAuthBackend" in AUTHENTICATION_BACKENDS
ONLY_LDAP = AUTHENTICATION_BACKENDS == ("zproject.backends.ZulipLDAPAuthBackend",)
USING_APACHE_SSO = "zproject.backends.ZulipRemoteUserBackend" in AUTHENTICATION_BACKENDS
ONLY_SSO = AUTHENTICATION_BACKENDS == ("zproject.backends.ZulipRemoteUserBackend",)

if CUSTOM_HOME_NOT_LOGGED_IN is not None:
    # We import this with a different name to avoid a mypy bug with
    # type-narrowed default parameter values.
    # https://github.com/python/mypy/issues/13087
    HOME_NOT_LOGGED_IN = CUSTOM_HOME_NOT_LOGGED_IN
elif ONLY_SSO:
    HOME_NOT_LOGGED_IN = "/accounts/login/sso/"
else:
    HOME_NOT_LOGGED_IN = "/login/"

AUTHENTICATION_BACKENDS += ("zproject.backends.ZulipDummyBackend",)

POPULATE_PROFILE_VIA_LDAP = bool(AUTH_LDAP_SERVER_URI)

if POPULATE_PROFILE_VIA_LDAP and not USING_LDAP:
    AUTHENTICATION_BACKENDS += ("zproject.backends.ZulipLDAPUserPopulator",)
else:
    POPULATE_PROFILE_VIA_LDAP = USING_LDAP or POPULATE_PROFILE_VIA_LDAP

if POPULATE_PROFILE_VIA_LDAP:
    import ldap

    if AUTH_LDAP_BIND_DN and ldap.OPT_REFERRALS not in AUTH_LDAP_CONNECTION_OPTIONS:
        # The default behavior of python-ldap (without setting option
        # `ldap.OPT_REFERRALS`) is to follow referrals, but anonymously.
        # If our original query was non-anonymous, that's unlikely to
        # work; skip the referral.
        #
        # The common case of this is that the server is Active Directory,
        # it's already given us the answer we need, and the referral is
        # just speculation about someplace else that has data our query
        # could in principle match.
        AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_REFERRALS] = 0

if REGISTER_LINK_DISABLED is None:
    # The default for REGISTER_LINK_DISABLED is a bit more
    # complicated: we want it to be disabled by default for people
    # using the LDAP backend that auto-creates users on login.
    REGISTER_LINK_DISABLED = ONLY_LDAP

########################################################################
# SOCIAL AUTHENTICATION SETTINGS
########################################################################

SOCIAL_AUTH_FIELDS_STORED_IN_SESSION = [
    "subdomain",
    "is_signup",
    "mobile_flow_otp",
    "desktop_flow_otp",
    "multiuse_object_key",
]
SOCIAL_AUTH_LOGIN_ERROR_URL = "/login/"

if SOCIAL_AUTH_SUBDOMAIN in ROOT_SUBDOMAIN_ALIASES:
    ROOT_SUBDOMAIN_ALIASES.remove(SOCIAL_AUTH_SUBDOMAIN)

# CLIENT is required by PSA's internal implementation. We name it
# SERVICES_ID to make things more readable in the configuration
# and our own custom backend code.
SOCIAL_AUTH_APPLE_CLIENT = SOCIAL_AUTH_APPLE_SERVICES_ID
SOCIAL_AUTH_APPLE_AUDIENCE = [
    id for id in [SOCIAL_AUTH_APPLE_CLIENT, SOCIAL_AUTH_APPLE_APP_ID] if id is not None
]

if PRODUCTION:
    SOCIAL_AUTH_APPLE_SECRET = get_from_file_if_exists("/etc/zulip/apple-auth-key.p8")
else:
    SOCIAL_AUTH_APPLE_SECRET = get_from_file_if_exists("zproject/dev_apple.key")

SOCIAL_AUTH_GITHUB_SECRET = get_secret("social_auth_github_secret")
SOCIAL_AUTH_GITLAB_SECRET = get_secret("social_auth_gitlab_secret")
SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET = get_secret("social_auth_azuread_oauth2_secret")

SOCIAL_AUTH_GITHUB_SCOPE = ["user:email"]
if SOCIAL_AUTH_GITHUB_ORG_NAME or SOCIAL_AUTH_GITHUB_TEAM_ID:
    SOCIAL_AUTH_GITHUB_SCOPE.append("read:org")
SOCIAL_AUTH_GITHUB_ORG_KEY = SOCIAL_AUTH_GITHUB_KEY
SOCIAL_AUTH_GITHUB_ORG_SECRET = SOCIAL_AUTH_GITHUB_SECRET
SOCIAL_AUTH_GITHUB_TEAM_KEY = SOCIAL_AUTH_GITHUB_KEY
SOCIAL_AUTH_GITHUB_TEAM_SECRET = SOCIAL_AUTH_GITHUB_SECRET

SOCIAL_AUTH_GOOGLE_SECRET = get_secret("social_auth_google_secret")
# Fallback to google-oauth settings in case social auth settings for
# Google are missing; this is for backwards-compatibility with older
# Zulip versions where /etc/zulip/settings.py has not been migrated yet.
GOOGLE_OAUTH2_CLIENT_SECRET = get_secret("google_oauth2_client_secret")
SOCIAL_AUTH_GOOGLE_KEY = SOCIAL_AUTH_GOOGLE_KEY or GOOGLE_OAUTH2_CLIENT_ID
SOCIAL_AUTH_GOOGLE_SECRET = SOCIAL_AUTH_GOOGLE_SECRET or GOOGLE_OAUTH2_CLIENT_SECRET

if PRODUCTION:
    SOCIAL_AUTH_SAML_SP_PUBLIC_CERT = get_from_file_if_exists("/etc/zulip/saml/zulip-cert.crt")
    SOCIAL_AUTH_SAML_SP_PRIVATE_KEY = get_from_file_if_exists(
        "/etc/zulip/saml/zulip-private-key.key"
    )

    if SOCIAL_AUTH_SAML_SP_PUBLIC_CERT and SOCIAL_AUTH_SAML_SP_PRIVATE_KEY:
        # If the certificates are set up, it's certainly desirable to sign
        # LogoutRequests and LogoutResponses unless explicitly specified otherwise
        # in the configuration.
        if "logoutRequestSigned" not in SOCIAL_AUTH_SAML_SECURITY_CONFIG:
            SOCIAL_AUTH_SAML_SECURITY_CONFIG["logoutRequestSigned"] = True
        if "logoutResponseSigned" not in SOCIAL_AUTH_SAML_SECURITY_CONFIG:
            SOCIAL_AUTH_SAML_SECURITY_CONFIG["logoutResponseSigned"] = True

if "signatureAlgorithm" not in SOCIAL_AUTH_SAML_SECURITY_CONFIG:
    # If the configuration doesn't explicitly specify the algorithm,
    # we set RSA1 with SHA256 to override the python3-saml default, which uses
    # insecure SHA1.
    default_signature_alg = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
    SOCIAL_AUTH_SAML_SECURITY_CONFIG["signatureAlgorithm"] = default_signature_alg

for idp_name, idp_dict in SOCIAL_AUTH_SAML_ENABLED_IDPS.items():
    if DEVELOPMENT:
        idp_dict["entity_id"] = get_secret("saml_entity_id", "")
        idp_dict["url"] = get_secret("saml_url", "")
        idp_dict["x509cert_path"] = "zproject/dev_saml.cert"

    # Set `x509cert` if not specified already; also support an override path.
    if "x509cert" in idp_dict:
        continue

    if "x509cert_path" in idp_dict:
        path = idp_dict["x509cert_path"]
    else:
        path = f"/etc/zulip/saml/idps/{idp_name}.crt"
    idp_dict["x509cert"] = get_from_file_if_exists(path)

SOCIAL_AUTH_PIPELINE = [
    "social_core.pipeline.social_auth.social_details",
    "zproject.backends.social_auth_associate_user",
    "zproject.backends.social_auth_finish",
]

########################################################################
# EMAIL SETTINGS
########################################################################

# Django setting. Not used in the Zulip codebase.
DEFAULT_FROM_EMAIL = ZULIP_ADMINISTRATOR

if EMAIL_BACKEND is not None:
    # If the server admin specified a custom email backend, use that.
    pass
elif DEVELOPMENT:
    # In the dev environment, emails are printed to the run-dev console.
    EMAIL_BACKEND = "zproject.email_backends.EmailLogBackEnd"
elif not EMAIL_HOST:
    # If an email host is not specified, fail gracefully
    WARN_NO_EMAIL = True
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_TIMEOUT = 15

if DEVELOPMENT:
    EMAIL_HOST = get_secret("email_host", "")
    EMAIL_PORT = int(get_secret("email_port", "25"))
    EMAIL_HOST_USER = get_secret("email_host_user", "")
    EMAIL_USE_TLS = get_secret("email_use_tls", "") == "true"

EMAIL_HOST_PASSWORD = get_secret("email_password")
EMAIL_GATEWAY_PASSWORD = get_secret("email_gateway_password")
AUTH_LDAP_BIND_PASSWORD = get_secret("auth_ldap_bind_password", "")

########################################################################
# MISC SETTINGS
########################################################################

if PRODUCTION:
    # Filter out user data
    DEFAULT_EXCEPTION_REPORTER_FILTER = "zerver.filters.ZulipExceptionReporterFilter"

# This is a debugging option only
PROFILE_ALL_REQUESTS = False

CROSS_REALM_BOT_EMAILS = {
    "notification-bot@zulip.com",
    "welcome-bot@zulip.com",
    "emailgateway@zulip.com",
}

MOBILE_NOTIFICATIONS_SHARDS = int(
    get_config("application_server", "mobile_notification_shards", "1")
)

TWO_FACTOR_PATCH_ADMIN = False

# Allow the environment to override the default DSN
SENTRY_DSN = os.environ.get("SENTRY_DSN", SENTRY_DSN)

SCIM_SERVICE_PROVIDER = {
    "USER_ADAPTER": "zerver.lib.scim.ZulipSCIMUser",
    "USER_FILTER_PARSER": "zerver.lib.scim_filter.ZulipUserFilterQuery",
    # NETLOC is actually overridden by the behavior of base_scim_location_getter,
    # but django-scim2 requires it to be set, even though it ends up not being used.
    # So we need to give it some value here, and EXTERNAL_HOST is the most generic.
    "NETLOC": EXTERNAL_HOST,
    "SCHEME": EXTERNAL_URI_SCHEME,
    "GET_EXTRA_MODEL_FILTER_KWARGS_GETTER": "zerver.lib.scim.get_extra_model_filter_kwargs_getter",
    "BASE_LOCATION_GETTER": "zerver.lib.scim.base_scim_location_getter",
    "AUTH_CHECK_MIDDLEWARE": "zerver.middleware.ZulipSCIMAuthCheckMiddleware",
    "AUTHENTICATION_SCHEMES": [
        {
            "type": "bearer",
            "name": "Bearer",
            "description": "Bearer token",
        },
    ],
}
