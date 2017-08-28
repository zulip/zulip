from __future__ import absolute_import
# Django settings for zulip project.
########################################################################
# Here's how settings for the Zulip project work:
#
# * settings.py contains non-site-specific and settings configuration
# for the Zulip Django app.
# * settings.py imports prod_settings.py, and any site-specific configuration
# belongs there.  The template for prod_settings.py is prod_settings_template.py
#
# See http://zulip.readthedocs.io/en/latest/settings.html for more information
#
########################################################################
from copy import deepcopy
import os
import platform
import time
import sys
import six.moves.configparser

from zerver.lib.db import TimeTrackingConnection
import zerver.lib.logging_util
import six

########################################################################
# INITIAL SETTINGS
########################################################################

DEPLOY_ROOT = os.path.join(os.path.realpath(os.path.dirname(__file__)), '..')

config_file = six.moves.configparser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether this instance of Zulip is running in a production environment.
PRODUCTION = config_file.has_option('machine', 'deploy_type')
DEVELOPMENT = not PRODUCTION

secrets_file = six.moves.configparser.RawConfigParser()
if PRODUCTION:
    secrets_file.read("/etc/zulip/zulip-secrets.conf")
else:
    secrets_file.read(os.path.join(DEPLOY_ROOT, "zproject/dev-secrets.conf"))

def get_secret(key):
    # type: (str) -> None
    if secrets_file.has_option('secrets', key):
        return secrets_file.get('secrets', key)
    return None

# Make this unique, and don't share it with anybody.
SECRET_KEY = get_secret("secret_key")

# A shared secret, used to authenticate different parts of the app to each other.
SHARED_SECRET = get_secret("shared_secret")

# We use this salt to hash a user's email into a filename for their user-uploaded
# avatar.  If this salt is discovered, attackers will only be able to determine
# that the owner of an email account has uploaded an avatar to Zulip, which isn't
# the end of the world.  Don't use the salt where there is more security exposure.
AVATAR_SALT = get_secret("avatar_salt")

# SERVER_GENERATION is used to track whether the server has been
# restarted for triggering browser clients to reload.
SERVER_GENERATION = int(time.time())

# Key to authenticate this server to zulip.org for push notifications, etc.
ZULIP_ORG_KEY = get_secret("zulip_org_key")
ZULIP_ORG_ID = get_secret("zulip_org_id")

if 'DEBUG' not in globals():
    # Uncomment end of next line to test CSS minification.
    # For webpack JS minification use tools/run_dev.py --minify
    DEBUG = DEVELOPMENT  # and platform.node() != 'your-machine'

if DEBUG:
    INTERNAL_IPS = ('127.0.0.1',)

# Detect whether we're running as a queue worker; this impacts the logging configuration.
if len(sys.argv) > 2 and sys.argv[0].endswith('manage.py') and sys.argv[1] == 'process_queue':
    IS_WORKER = True
else:
    IS_WORKER = False


# This is overridden in test_settings.py for the test suites
TEST_SUITE = False
# The new user tutorial is enabled by default, but disabled for client tests.
TUTORIAL_ENABLED = True
# This is overridden in test_settings.py for the test suites
CASPER_TESTS = False

# Import variables like secrets from the prod_settings file
# Import prod_settings after determining the deployment/machine type
if PRODUCTION:
    from .prod_settings import *
else:
    from .dev_settings import *

########################################################################
# DEFAULT VALUES FOR SETTINGS
########################################################################

# For any settings that are not defined in prod_settings.py,
# we want to initialize them to sane default
DEFAULT_SETTINGS = {'TWITTER_CONSUMER_KEY': '',
                    'TWITTER_CONSUMER_SECRET': '',
                    'TWITTER_ACCESS_TOKEN_KEY': '',
                    'TWITTER_ACCESS_TOKEN_SECRET': '',
                    'EMAIL_GATEWAY_PATTERN': '',
                    'EMAIL_GATEWAY_EXAMPLE': '',
                    'EMAIL_GATEWAY_BOT': None,
                    'EMAIL_GATEWAY_LOGIN': None,
                    'EMAIL_GATEWAY_PASSWORD': None,
                    'EMAIL_GATEWAY_IMAP_SERVER': None,
                    'EMAIL_GATEWAY_IMAP_PORT': None,
                    'EMAIL_GATEWAY_IMAP_FOLDER': None,
                    'EMAIL_GATEWAY_EXTRA_PATTERN_HACK': None,
                    'EMAIL_HOST': None,
                    'EMAIL_BACKEND': None,
                    'NOREPLY_EMAIL_ADDRESS': "noreply@" + EXTERNAL_HOST.split(":")[0],
                    'STAGING': False,
                    'S3_KEY': '',
                    'S3_SECRET_KEY': '',
                    'S3_AVATAR_BUCKET': '',
                    'LOCAL_UPLOADS_DIR': None,
                    'DATA_UPLOAD_MAX_MEMORY_SIZE': 25 * 1024 * 1024,
                    'MAX_FILE_UPLOAD_SIZE': 25,
                    'MAX_AVATAR_FILE_SIZE': 5,
                    'MAX_ICON_FILE_SIZE': 5,
                    'MAX_EMOJI_FILE_SIZE': 5,
                    'ERROR_REPORTING': True,
                    'BROWSER_ERROR_REPORTING': False,
                    'STAGING_ERROR_NOTIFICATIONS': False,
                    'EVENT_LOGS_ENABLED': False,
                    'SAVE_FRONTEND_STACKTRACES': False,
                    'JWT_AUTH_KEYS': {},
                    'NAME_CHANGES_DISABLED': False,
                    'DEPLOYMENT_ROLE_NAME': "",
                    'RABBITMQ_HOST': 'localhost',
                    'RABBITMQ_USERNAME': 'zulip',
                    'MEMCACHED_LOCATION': '127.0.0.1:11211',
                    'RATE_LIMITING': True,
                    'REDIS_HOST': '127.0.0.1',
                    'REDIS_PORT': 6379,
                    # The following bots only exist in non-VOYAGER installs
                    'ERROR_BOT': None,
                    'NEW_USER_BOT': None,
                    'NAGIOS_STAGING_SEND_BOT': None,
                    'NAGIOS_STAGING_RECEIVE_BOT': None,
                    'APNS_CERT_FILE': None,
                    'APNS_KEY_FILE': None,
                    'APNS_SANDBOX': True,
                    'ANDROID_GCM_API_KEY': None,
                    'INITIAL_PASSWORD_SALT': None,
                    'FEEDBACK_BOT': 'feedback@zulip.com',
                    'FEEDBACK_BOT_NAME': 'Zulip Feedback Bot',
                    'ADMINS': '',
                    'INLINE_IMAGE_PREVIEW': True,
                    'INLINE_URL_EMBED_PREVIEW': False,
                    'CAMO_URI': '',
                    'ENABLE_FEEDBACK': PRODUCTION,
                    'SEND_MISSED_MESSAGE_EMAILS_AS_USER': False,
                    'SEND_LOGIN_EMAILS': True,
                    'SERVER_EMAIL': None,
                    'FEEDBACK_EMAIL': None,
                    'FEEDBACK_STREAM': None,
                    'WELCOME_EMAIL_SENDER': None,
                    'EMAIL_DELIVERER_DISABLED': False,
                    'ENABLE_GRAVATAR': True,
                    'DEFAULT_AVATAR_URI': '/static/images/default-avatar.png',
                    'AUTH_LDAP_SERVER_URI': "",
                    'LDAP_EMAIL_ATTR': None,
                    'EXTERNAL_URI_SCHEME': "https://",
                    'ZULIP_COM': False,
                    'SHOW_OSS_ANNOUNCEMENT': False,
                    'REGISTER_LINK_DISABLED': False,
                    'LOGIN_LINK_DISABLED': False,
                    'ABOUT_LINK_DISABLED': False,
                    'FIND_TEAM_LINK_DISABLED': True,
                    'CUSTOM_LOGO_URL': None,
                    'VERBOSE_SUPPORT_OFFERS': False,
                    'STATSD_HOST': '',
                    'OPEN_REALM_CREATION': False,
                    'REALMS_HAVE_SUBDOMAINS': True,
                    'ROOT_DOMAIN_LANDING_PAGE': False,
                    'ROOT_SUBDOMAIN_ALIASES': ["www"],
                    'REMOTE_POSTGRES_HOST': '',
                    'REMOTE_POSTGRES_SSLMODE': '',
                    # Default GOOGLE_CLIENT_ID to the value needed for Android auth to work
                    'GOOGLE_CLIENT_ID': '835904834568-77mtr5mtmpgspj9b051del9i9r5t4g4n.apps.googleusercontent.com',
                    'SOCIAL_AUTH_GITHUB_KEY': None,
                    'SOCIAL_AUTH_GITHUB_ORG_NAME': None,
                    'SOCIAL_AUTH_GITHUB_TEAM_ID': None,
                    'GOOGLE_OAUTH2_CLIENT_ID': None,
                    'SOCIAL_AUTH_FIELDS_STORED_IN_SESSION': ['subdomain', 'is_signup'],
                    'DBX_APNS_CERT_FILE': None,
                    'DBX_APNS_KEY_FILE': None,
                    'PERSONAL_ZMIRROR_SERVER': None,
                    # Structurally, we will probably eventually merge
                    # analytics into part of the main server, rather
                    # than a separate app.
                    'EXTRA_INSTALLED_APPS': ['analytics'],
                    'CONFIRMATION_LINK_DEFAULT_VALIDITY_DAYS': 1,
                    'INVITATION_LINK_VALIDITY_DAYS': 10,
                    'REALM_CREATION_LINK_VALIDITY_DAYS': 7,
                    'TERMS_OF_SERVICE': None,
                    'PRIVACY_POLICY': None,
                    'TOS_VERSION': None,
                    'SYSTEM_ONLY_REALMS': {"zulip"},
                    'FIRST_TIME_TOS_TEMPLATE': None,
                    'USING_PGROONGA': False,
                    'POST_MIGRATION_CACHE_FLUSHING': False,
                    'ENABLE_FILE_LINKS': False,
                    'USE_WEBSOCKETS': True,
                    'ANALYTICS_LOCK_DIR': "/home/zulip/deployments/analytics-lock-dir",
                    'PASSWORD_MIN_LENGTH': 6,
                    'PASSWORD_MIN_ZXCVBN_QUALITY': 0.5,
                    'OFFLINE_THRESHOLD_SECS': 5 * 60,
                    'PUSH_NOTIFICATION_BOUNCER_URL': None,
                    }

for setting_name, setting_val in six.iteritems(DEFAULT_SETTINGS):
    if setting_name not in vars():
        vars()[setting_name] = setting_val

# Extend ALLOWED_HOSTS with localhost (needed to RPC to Tornado).
ALLOWED_HOSTS += ['127.0.0.1', 'localhost']

# These are the settings that we will check that the user has filled in for
# production deployments before starting the app.  It consists of a series
# of pairs of (setting name, default value that it must be changed from)
REQUIRED_SETTINGS = [("EXTERNAL_HOST", "zulip.example.com"),
                     ("ZULIP_ADMINISTRATOR", "zulip-admin@example.com"),
                     # SECRET_KEY doesn't really need to be here, in
                     # that we set it automatically, but just in
                     # case, it seems worth having in this list
                     ("SECRET_KEY", ""),
                     ("AUTHENTICATION_BACKENDS", ()),
                     ]

if ADMINS == "":
    ADMINS = (("Zulip Administrator", ZULIP_ADMINISTRATOR),)
MANAGERS = ADMINS

# Voyager is a production zulip server that is not zulip.com or
# staging.zulip.com VOYAGER is the standalone all-on-one-server
# production deployment model for based on the original Zulip
# ENTERPRISE implementation.  We expect most users of the open source
# project will be using VOYAGER=True in production.
VOYAGER = PRODUCTION and not ZULIP_COM

########################################################################
# STANDARD DJANGO SETTINGS
########################################################################

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# The ID, as an integer, of the current site in the django_site database table.
# This is used so that application data can hook into specific site(s) and a
# single database can manage content for multiple sites.
#
# We set this site's string_id to 'zulip' in populate_db.
SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

DEPLOY_ROOT = os.path.join(os.path.realpath(os.path.dirname(__file__)), '..')
# this directory will be used to store logs for development environment
DEVELOPMENT_LOG_DIRECTORY = os.path.join(DEPLOY_ROOT, 'var', 'log')
# Make redirects work properly behind a reverse proxy
USE_X_FORWARDED_HOST = True

MIDDLEWARE = (
    # With the exception of it's dependencies,
    # our logging middleware should be the top middleware item.
    'zerver.middleware.TagRequests',
    'zerver.middleware.SetRemoteAddrFromForwardedFor',
    'zerver.middleware.LogRequests',
    'zerver.middleware.JsonErrorHandler',
    'zerver.middleware.RateLimitMiddleware',
    'zerver.middleware.FlushDisplayRecipientCache',
    'django.middleware.common.CommonMiddleware',
    'zerver.middleware.SessionHostDomainMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ANONYMOUS_USER_ID = None

AUTH_USER_MODEL = "zerver.UserProfile"

TEST_RUNNER = 'zerver.lib.test_runner.Runner'

ROOT_URLCONF = 'zproject.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'zproject.wsgi.application'

# A site can include additional installed apps via the
# EXTRA_INSTALLED_APPS setting
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'confirmation',
    'pipeline',
    'webpack_loader',
    'zerver',
    'social_django',
]
if USING_PGROONGA:
    INSTALLED_APPS += ['pgroonga']
INSTALLED_APPS += EXTRA_INSTALLED_APPS

ZILENCER_ENABLED = 'zilencer' in INSTALLED_APPS

# Base URL of the Tornado server
# We set it to None when running backend tests or populate_db.
# We override the port number when running frontend tests.
TORNADO_SERVER = 'http://127.0.0.1:9993'
RUNNING_INSIDE_TORNADO = False
AUTORELOAD = DEBUG

########################################################################
# DATABASE CONFIGURATION
########################################################################

DATABASES = {"default": {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'zulip',
    'USER': 'zulip',
    'PASSWORD': '',  # Authentication done via certificates
    'HOST': '',  # Host = '' => connect through a local socket
    'SCHEMA': 'zulip',
    'CONN_MAX_AGE': 600,
    'OPTIONS': {
        'connection_factory': TimeTrackingConnection
    },
}}

if DEVELOPMENT:
    LOCAL_DATABASE_PASSWORD = get_secret("local_database_password")
    DATABASES["default"].update({
        'PASSWORD': LOCAL_DATABASE_PASSWORD,
        'HOST': 'localhost'
    })
elif REMOTE_POSTGRES_HOST != '':
    DATABASES['default'].update({
        'HOST': REMOTE_POSTGRES_HOST,
    })
    if get_secret("postgres_password") is not None:
        DATABASES['default'].update({
            'PASSWORD': get_secret("postgres_password"),
        })
    if REMOTE_POSTGRES_SSLMODE != '':
        DATABASES['default']['OPTIONS']['sslmode'] = REMOTE_POSTGRES_SSLMODE
    else:
        DATABASES['default']['OPTIONS']['sslmode'] = 'verify-full'

if USING_PGROONGA:
    # We need to have "pgroonga" schema before "pg_catalog" schema in
    # the PostgreSQL search path, because "pgroonga" schema overrides
    # the "@@" operator from "pg_catalog" schema, and "pg_catalog"
    # schema is searched first if not specified in the search path.
    # See also: http://www.postgresql.org/docs/current/static/runtime-config-client.html
    pg_options = '-c search_path=%(SCHEMA)s,zulip,public,pgroonga,pg_catalog' % \
        DATABASES['default']
    DATABASES['default']['OPTIONS']['options'] = pg_options

########################################################################
# RABBITMQ CONFIGURATION
########################################################################

USING_RABBITMQ = True
RABBITMQ_PASSWORD = get_secret("rabbitmq_password")

########################################################################
# CACHING CONFIGURATION
########################################################################

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': MEMCACHED_LOCATION,
        'TIMEOUT': 3600,
        'OPTIONS': {
            'verify_keys': True,
            'tcp_nodelay': True,
            'retry_timeout': 1,
        }
    },
    'database': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'third_party_api_results',
        # Basically never timeout.  Setting to 0 isn't guaranteed
        # to work, see https://code.djangoproject.com/ticket/9595
        'TIMEOUT': 2000000000,
        'OPTIONS': {
            'MAX_ENTRIES': 100000000,
            'CULL_FREQUENCY': 10,
        }
    },
}

########################################################################
# REDIS-BASED RATE LIMITING CONFIGURATION
########################################################################

RATE_LIMITING_RULES = [
    (60, 100),  # 100 requests max every minute
]
DEBUG_RATE_LIMITING = DEBUG
REDIS_PASSWORD = get_secret('redis_password')

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

try:
    # For get_updates hostname sharding.
    domain = config_file.get('django', 'cookie_domain')
    SESSION_COOKIE_DOMAIN = '.' + domain
    CSRF_COOKIE_DOMAIN = '.' + domain
except six.moves.configparser.Error:
    # Failing here is OK
    pass

# Prevent Javascript from reading the CSRF token from cookies.  Our code gets
# the token from the DOM, which means malicious code could too.  But hiding the
# cookie will slow down some attackers.
CSRF_COOKIE_PATH = '/;HttpOnly'
CSRF_FAILURE_VIEW = 'zerver.middleware.csrf_failure'

if DEVELOPMENT:
    # Use fast password hashing for creating testing users when not
    # PRODUCTION.  Saves a bunch of time.
    PASSWORD_HASHERS = (
        'django.contrib.auth.hashers.SHA1PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2PasswordHasher'
    )
    # Also we auto-generate passwords for the default users which you
    # can query using ./manage.py print_initial_password
    INITIAL_PASSWORD_SALT = get_secret("initial_password_salt")
else:
    # For production, use the best password hashing algorithm: Argon2
    # Zulip was originally on PBKDF2 so we need it for compatibility
    PASSWORD_HASHERS = ('django.contrib.auth.hashers.Argon2PasswordHasher',
                        'django.contrib.auth.hashers.PBKDF2PasswordHasher')

########################################################################
# API/BOT SETTINGS
########################################################################

if "EXTERNAL_API_PATH" not in vars():
    EXTERNAL_API_PATH = EXTERNAL_HOST + "/api"
EXTERNAL_API_URI = EXTERNAL_URI_SCHEME + EXTERNAL_API_PATH
ROOT_DOMAIN_URI = EXTERNAL_URI_SCHEME + EXTERNAL_HOST

if "NAGIOS_BOT_HOST" not in vars():
    NAGIOS_BOT_HOST = EXTERNAL_HOST

S3_KEY = get_secret("s3_key")
S3_SECRET_KEY = get_secret("s3_secret_key")

# GCM tokens are IP-whitelisted; if we deploy to additional
# servers you will need to explicitly add their IPs here:
# https://cloud.google.com/console/project/apps~zulip-android/apiui/credential
ANDROID_GCM_API_KEY = get_secret("android_gcm_api_key")

GOOGLE_OAUTH2_CLIENT_SECRET = get_secret('google_oauth2_client_secret')

DROPBOX_APP_KEY = get_secret("dropbox_app_key")

MAILCHIMP_API_KEY = get_secret("mailchimp_api_key")

# Twitter API credentials
# Secrecy not required because its only used for R/O requests.
# Please don't make us go over our rate limit.
TWITTER_CONSUMER_KEY = get_secret("twitter_consumer_key")
TWITTER_CONSUMER_SECRET = get_secret("twitter_consumer_secret")
TWITTER_ACCESS_TOKEN_KEY = get_secret("twitter_access_token_key")
TWITTER_ACCESS_TOKEN_SECRET = get_secret("twitter_access_token_secret")

# These are the bots that Zulip sends automated messages as.
INTERNAL_BOTS = [{'var_name': 'NOTIFICATION_BOT',
                  'email_template': 'notification-bot@%s',
                  'name': 'Notification Bot'},
                 {'var_name': 'EMAIL_GATEWAY_BOT',
                  'email_template': 'emailgateway@%s',
                  'name': 'Email Gateway'},
                 {'var_name': 'NAGIOS_SEND_BOT',
                  'email_template': 'nagios-send-bot@%s',
                  'name': 'Nagios Send Bot'},
                 {'var_name': 'NAGIOS_RECEIVE_BOT',
                  'email_template': 'nagios-receive-bot@%s',
                  'name': 'Nagios Receive Bot'},
                 {'var_name': 'WELCOME_BOT',
                  'email_template': 'welcome-bot@%s',
                  'name': 'Welcome Bot'}]

if PRODUCTION:
    INTERNAL_BOTS += [
        {'var_name': 'NAGIOS_STAGING_SEND_BOT',
         'email_template': 'nagios-staging-send-bot@%s',
         'name': 'Nagios Staging Send Bot'},
        {'var_name': 'NAGIOS_STAGING_RECEIVE_BOT',
         'email_template': 'nagios-staging-receive-bot@%s',
         'name': 'Nagios Staging Receive Bot'},
    ]

INTERNAL_BOT_DOMAIN = "zulip.com"

# Set the realm-specific bot names
for bot in INTERNAL_BOTS:
    if vars().get(bot['var_name']) is None:
        bot_email = bot['email_template'] % (INTERNAL_BOT_DOMAIN,)
        vars()[bot['var_name']] = bot_email

if EMAIL_GATEWAY_PATTERN != "":
    EMAIL_GATEWAY_EXAMPLE = EMAIL_GATEWAY_PATTERN % ("support+abcdefg",)

DEPLOYMENT_ROLE_KEY = get_secret("deployment_role_key")

########################################################################
# STATSD CONFIGURATION
########################################################################

# Statsd is not super well supported; if you want to use it you'll need
# to set STATSD_HOST and STATSD_PREFIX.
if STATSD_HOST != '':
    INSTALLED_APPS += ['django_statsd']
    STATSD_PORT = 8125
    STATSD_CLIENT = 'django_statsd.clients.normal'

########################################################################
# CAMO HTTPS CACHE CONFIGURATION
########################################################################

if CAMO_URI != '':
    # This needs to be synced with the Camo installation
    CAMO_KEY = get_secret("camo_key")

########################################################################
# STATIC CONTENT AND MINIFICATION SETTINGS
########################################################################

STATIC_URL = '/static/'

# ZulipStorage is a modified version of PipelineCachedStorage,
# and, like that class, it inserts a file hash into filenames
# to prevent the browser from using stale files from cache.
#
# Unlike PipelineStorage, it requires the files to exist in
# STATIC_ROOT even for dev servers.  So we only use
# ZulipStorage when not DEBUG.

# This is the default behavior from Pipeline, but we set it
# here so that urls.py can read it.
PIPELINE_ENABLED = not DEBUG

if DEBUG:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'
    STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'pipeline.finders.PipelineFinder',
    )
    if PIPELINE_ENABLED:
        STATIC_ROOT = os.path.abspath('prod-static/serve')
    else:
        STATIC_ROOT = os.path.abspath('static/')
else:
    STATICFILES_STORAGE = 'zerver.storage.ZulipStorage'
    STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'pipeline.finders.PipelineFinder',
    )
    if PRODUCTION:
        STATIC_ROOT = '/home/zulip/prod-static'
    else:
        STATIC_ROOT = os.path.abspath('prod-static/serve')

# If changing this, you need to also the hack modifications to this in
# our compilemessages management command.
LOCALE_PATHS = (os.path.join(STATIC_ROOT, 'locale'),)

# We want all temporary uploaded files to be stored on disk.
FILE_UPLOAD_MAX_MEMORY_SIZE = 0

STATICFILES_DIRS = ['static/']
STATIC_HEADER_FILE = 'zerver/static_header.txt'

# To use minified files in dev, set PIPELINE_ENABLED = True.  For the full
# cache-busting behavior, you must also set DEBUG = False.
#
# You will need to run update-prod-static after changing
# static files.
#
# Useful reading on how this works is in
# https://zulip.readthedocs.io/en/latest/front-end-build-process.html

PIPELINE = {
    'PIPELINE_ENABLED': PIPELINE_ENABLED,
    'CSS_COMPRESSOR': 'pipeline.compressors.yui.YUICompressor',
    'YUI_BINARY': '/usr/bin/env yui-compressor',
    'STYLESHEETS': {
        # If you add a style here, please update stylesheets()
        # in frontend_tests/zjsunit/output.js as needed.
        'activity': {
            'source_filenames': ('styles/activity.css',),
            'output_filename': 'min/activity.css'
        },
        'stats': {
            'source_filenames': ('styles/stats.css',),
            'output_filename': 'min/stats.css'
        },
        'portico': {
            'source_filenames': (
                'third/zocial/zocial.css',
                'styles/portico.css',
                'styles/portico-signin.css',
                'styles/pygments.css',
                'third/thirdparty-fonts.css',
                'styles/fonts.css',
            ),
            'output_filename': 'min/portico.css'
        },
        'landing-page': {
            'source_filenames': (
                'styles/landing-page.css',
            ),
            'output_filename': 'min/landing.css'
        },
        # Two versions of the app CSS exist because of QTBUG-3467
        'app-fontcompat': {
            'source_filenames': (
                'third/bootstrap-notify/css/bootstrap-notify.css',
                'third/spectrum/spectrum.css',
                'third/thirdparty-fonts.css',
                'styles/components.css',
                'styles/zulip.css',
                'styles/alerts.css',
                'styles/settings.css',
                'styles/subscriptions.css',
                'styles/drafts.css',
                'styles/informational-overlays.css',
                'styles/compose.css',
                'styles/reactions.css',
                'styles/left-sidebar.css',
                'styles/right-sidebar.css',
                'styles/lightbox.css',
                'styles/popovers.css',
                'styles/pygments.css',
                'styles/media.css',
                'styles/typing_notifications.css',
                'styles/hotspots.css',
                # We don't want fonts.css on QtWebKit, so its omitted here
            ),
            'output_filename': 'min/app-fontcompat.css'
        },
        'app': {
            'source_filenames': (
                'third/bootstrap-notify/css/bootstrap-notify.css',
                'third/spectrum/spectrum.css',
                'third/thirdparty-fonts.css',
                'node_modules/katex/dist/katex.css',
                'styles/components.css',
                'styles/zulip.css',
                'styles/alerts.css',
                'styles/settings.css',
                'styles/subscriptions.css',
                'styles/drafts.css',
                'styles/informational-overlays.css',
                'styles/compose.css',
                'styles/reactions.css',
                'styles/left-sidebar.css',
                'styles/right-sidebar.css',
                'styles/lightbox.css',
                'styles/popovers.css',
                'styles/pygments.css',
                'styles/fonts.css',
                'styles/media.css',
                'styles/typing_notifications.css',
                'styles/hotspots.css',
            ),
            'output_filename': 'min/app.css'
        },
        'common': {
            'source_filenames': (
                'third/bootstrap/css/bootstrap.css',
                'third/bootstrap/css/bootstrap-btn.css',
                'third/bootstrap/css/bootstrap-responsive.css',
                'node_modules/perfect-scrollbar/dist/css/perfect-scrollbar.css',
            ),
            'output_filename': 'min/common.css'
        },
        'apple_sprite': {
            'source_filenames': (
                'generated/emoji/google_sprite.css',
            ),
            'output_filename': 'min/google_sprite.css',
        },
        'emojione_sprite': {
            'source_filenames': (
                'generated/emoji/google_sprite.css',
            ),
            'output_filename': 'min/google_sprite.css',
        },
        'google_sprite': {
            'source_filenames': (
                'generated/emoji/google_sprite.css',
            ),
            'output_filename': 'min/google_sprite.css',
        },
        'twitter_sprite': {
            'source_filenames': (
                'generated/emoji/google_sprite.css',
            ),
            'output_filename': 'min/google_sprite.css',
        },
    },
    'JAVASCRIPT': {},
}

# Useful reading on how this works is in
# https://zulip.readthedocs.io/en/latest/front-end-build-process.html
JS_SPECS = {
    'app': {
        'source_filenames': [
            'third/bootstrap-notify/js/bootstrap-notify.js',
            'third/html5-formdata/formdata.js',
            'node_modules/jquery-validation/dist/jquery.validate.js',
            'node_modules/clipboard/dist/clipboard.js',
            'third/jquery-form/jquery.form.js',
            'third/jquery-filedrop/jquery.filedrop.js',
            'third/jquery-caret/jquery.caret.1.5.2.js',
            'node_modules/xdate/src/xdate.js',
            'third/jquery-throttle-debounce/jquery.ba-throttle-debounce.js',
            'third/jquery-idle/jquery.idle.js',
            'third/jquery-autosize/jquery.autosize.js',
            'node_modules/perfect-scrollbar/dist/js/perfect-scrollbar.jquery.js',
            'third/lazyload/lazyload.js',
            'third/spectrum/spectrum.js',
            'third/sockjs/sockjs-0.3.4.js',
            'node_modules/string.prototype.codepointat/codepointat.js',
            'node_modules/winchan/winchan.js',
            'node_modules/handlebars/dist/handlebars.runtime.js',
            'third/marked/lib/marked.js',
            'generated/emoji/emoji_codes.js',
            'generated/pygments_data.js',
            'templates/compiled.js',
            'js/feature_flags.js',
            'js/loading.js',
            'js/util.js',
            'js/dynamic_text.js',
            'js/lightbox_canvas.js',
            'js/rtl.js',
            'js/dict.js',
            'js/components.js',
            'js/localstorage.js',
            'js/drafts.js',
            'js/channel.js',
            'js/setup.js',
            'js/unread_ui.js',
            'js/unread_ops.js',
            'js/muting.js',
            'js/muting_ui.js',
            'js/message_viewport.js',
            'js/rows.js',
            'js/people.js',
            'js/unread.js',
            'js/topic_list.js',
            'js/pm_list.js',
            'js/pm_conversations.js',
            'js/recent_senders.js',
            'js/stream_sort.js',
            'js/topic_generator.js',
            'js/top_left_corner.js',
            'js/stream_list.js',
            'js/filter.js',
            'js/message_list_view.js',
            'js/message_list.js',
            'js/message_live_update.js',
            'js/narrow_state.js',
            'js/narrow.js',
            'js/reload.js',
            'js/compose_fade.js',
            'js/fenced_code.js',
            'js/markdown.js',
            'js/echo.js',
            'js/socket.js',
            'js/sent_messages.js',
            'js/compose_state.js',
            'js/compose_actions.js',
            'js/compose.js',
            'js/stream_color.js',
            'js/stream_data.js',
            'js/topic_data.js',
            'js/stream_muting.js',
            'js/stream_events.js',
            'js/stream_create.js',
            'js/stream_edit.js',
            'js/subs.js',
            'js/message_edit.js',
            'js/condense.js',
            'js/resize.js',
            'js/list_render.js',
            'js/floating_recipient_bar.js',
            'js/lightbox.js',
            'js/ui_report.js',
            'js/ui.js',
            'js/ui_util.js',
            'js/pointer.js',
            'js/click_handlers.js',
            'js/scroll_bar.js',
            'js/gear_menu.js',
            'js/copy_and_paste.js',
            'js/stream_popover.js',
            'js/popovers.js',
            'js/overlays.js',
            'js/typeahead_helper.js',
            'js/search_suggestion.js',
            'js/search.js',
            'js/composebox_typeahead.js',
            'js/navigate.js',
            'js/list_util.js',
            'js/hotkey.js',
            'js/favicon.js',
            'js/notifications.js',
            'js/hash_util.js',
            'js/hashchange.js',
            'js/invite.js',
            'js/message_flags.js',
            'js/alert_words.js',
            'js/alert_words_ui.js',
            'js/attachments_ui.js',
            'js/message_store.js',
            'js/message_util.js',
            'js/message_events.js',
            'js/message_fetch.js',
            'js/server_events.js',
            'js/server_events_dispatch.js',
            'js/zulip.js',
            'js/presence.js',
            'js/activity.js',
            'js/user_events.js',
            'js/colorspace.js',
            'js/timerender.js',
            'js/tutorial.js',
            'js/hotspots.js',
            'js/templates.js',
            'js/upload_widget.js',
            'js/avatar.js',
            'js/realm_icon.js',
            'js/settings_account.js',
            'js/settings_display.js',
            'js/settings_notifications.js',
            'js/settings_bots.js',
            'js/settings_muting.js',
            'js/settings_lab.js',
            'js/settings_sections.js',
            'js/settings_emoji.js',
            'js/settings_org.js',
            'js/settings_users.js',
            'js/settings_streams.js',
            'js/settings_filters.js',
            'js/settings.js',
            'js/admin_sections.js',
            'js/admin.js',
            'js/tab_bar.js',
            'js/emoji.js',
            'js/custom_markdown.js',
            'js/bot_data.js',
            'js/reactions.js',
            'js/typing.js',
            'js/typing_status.js',
            'js/typing_data.js',
            'js/typing_events.js',
            'js/ui_init.js',
            'js/emoji_picker.js',
            'js/compose_ui.js',
        ],
        'output_filename': 'min/app.js'
    },
    # We also want to minify sockjs separately for the sockjs iframe transport
    'sockjs': {
        'source_filenames': ['third/sockjs/sockjs-0.3.4.js'],
        'output_filename': 'min/sockjs-0.3.4.min.js'
    }
}

app_srcs = JS_SPECS['app']['source_filenames']
if DEVELOPMENT:
    WEBPACK_STATS_FILE = os.path.join('var', 'webpack-stats-dev.json')
else:
    WEBPACK_STATS_FILE = 'webpack-stats-production.json'
WEBPACK_LOADER = {
    'DEFAULT': {
        'BUNDLE_DIR_NAME': 'webpack-bundles/',
        'STATS_FILE': os.path.join(DEPLOY_ROOT, WEBPACK_STATS_FILE),
    }
}

########################################################################
# TEMPLATES SETTINGS
########################################################################

# List of callables that know how to import templates from various sources.
LOADERS = [
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
]
if PRODUCTION:
    # Template caching is a significant performance win in production.
    LOADERS = [('django.template.loaders.cached.Loader', LOADERS)]

base_template_engine_settings = {
    'BACKEND': 'django.template.backends.jinja2.Jinja2',
    'OPTIONS': {
        'environment': 'zproject.jinja2.environment',
        'extensions': [
            'jinja2.ext.i18n',
            'jinja2.ext.autoescape',
            'pipeline.jinja2.PipelineExtension',
            'webpack_loader.contrib.jinja2ext.WebpackExtension',
        ],
        'context_processors': [
            'zerver.context_processors.zulip_default_context',
            'zerver.context_processors.add_metrics',
            'django.template.context_processors.i18n',
        ],
    },
}

default_template_engine_settings = deepcopy(base_template_engine_settings)
default_template_engine_settings.update({
    'NAME': 'Jinja2',
    'DIRS': [
        # The main templates directory
        os.path.join(DEPLOY_ROOT, 'templates'),
        # The webhook integration templates
        os.path.join(DEPLOY_ROOT, 'zerver', 'webhooks'),
        # The python-zulip-api:zulip_bots package templates
        os.path.join(STATIC_ROOT, 'generated', 'bots'),
    ],
    'APP_DIRS': True,
})

non_html_template_engine_settings = deepcopy(base_template_engine_settings)
non_html_template_engine_settings.update({
    'NAME': 'Jinja2_plaintext',
    'DIRS': [os.path.join(DEPLOY_ROOT, 'templates')],
    'APP_DIRS': False,
})
non_html_template_engine_settings['OPTIONS'].update({
    'autoescape': False,
    'trim_blocks': True,
    'lstrip_blocks': True,
})

# The order here is important; get_template and related/parent functions try
# the template engines in order until one succeeds.
TEMPLATES = [
    default_template_engine_settings,
    non_html_template_engine_settings,
]
########################################################################
# LOGGING SETTINGS
########################################################################

ZULIP_PATHS = [
    ("SERVER_LOG_PATH", "/var/log/zulip/server.log"),
    ("ERROR_FILE_LOG_PATH", "/var/log/zulip/errors.log"),
    ("MANAGEMENT_LOG_PATH", "/var/log/zulip/manage.log"),
    ("WORKER_LOG_PATH", "/var/log/zulip/workers.log"),
    ("PERSISTENT_QUEUE_FILENAME", "/home/zulip/tornado/event_queues.pickle"),
    ("JSON_PERSISTENT_QUEUE_FILENAME", "/home/zulip/tornado/event_queues.json"),
    ("EMAIL_LOG_PATH", "/var/log/zulip/send_email.log"),
    ("EMAIL_MIRROR_LOG_PATH", "/var/log/zulip/email_mirror.log"),
    ("EMAIL_DELIVERER_LOG_PATH", "/var/log/zulip/email-deliverer.log"),
    ("LDAP_SYNC_LOG_PATH", "/var/log/zulip/sync_ldap_user_data.log"),
    ("QUEUE_ERROR_DIR", "/var/log/zulip/queue_error"),
    ("STATS_DIR", "/home/zulip/stats"),
    ("DIGEST_LOG_PATH", "/var/log/zulip/digest.log"),
    ("ANALYTICS_LOG_PATH", "/var/log/zulip/analytics.log"),
    ("API_KEY_ONLY_WEBHOOK_LOG_PATH", "/var/log/zulip/webhooks_errors.log"),
    ("SOFT_DEACTIVATION_LOG_PATH", "/var/log/zulip/soft_deactivation.log"),
]

# The Event log basically logs most significant database changes,
# which can be useful for debugging.
if EVENT_LOGS_ENABLED:
    ZULIP_PATHS.append(("EVENT_LOG_DIR", "/home/zulip/logs/event_log"))
else:
    EVENT_LOG_DIR = None

for (var, path) in ZULIP_PATHS:
    if DEVELOPMENT:
        # if DEVELOPMENT, store these files in the Zulip checkout
        path = os.path.join(DEVELOPMENT_LOG_DIRECTORY, os.path.basename(path))
        # only `JSON_PERSISTENT_QUEUE_FILENAME` will be stored in `var`
        if var == 'JSON_PERSISTENT_QUEUE_FILENAME':
            path = os.path.join(os.path.join(DEPLOY_ROOT, 'var'), os.path.basename(path))
    vars()[var] = path

ZULIP_WORKER_TEST_FILE = '/tmp/zulip-worker-test-file'


if IS_WORKER:
    FILE_LOG_PATH = WORKER_LOG_PATH
else:
    FILE_LOG_PATH = SERVER_LOG_PATH
# Used for test_logging_handlers
LOGGING_NOT_DISABLED = True

DEFAULT_ZULIP_HANDLERS = (
    (['zulip_admins'] if ERROR_REPORTING else []) +
    ['console', 'file', 'errors_file']
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname)-8s %(message)s'
        }
    },
    'filters': {
        'ZulipLimiter': {
            '()': 'zerver.lib.logging_util.ZulipLimiter',
        },
        'EmailLimiter': {
            '()': 'zerver.lib.logging_util.EmailLimiter',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'nop': {
            '()': 'zerver.lib.logging_util.ReturnTrue',
        },
        'require_logging_enabled': {
            '()': 'zerver.lib.logging_util.ReturnEnabled',
        },
        'require_really_deployed': {
            '()': 'zerver.lib.logging_util.RequireReallyDeployed',
        },
        'skip_200_and_304': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': zerver.lib.logging_util.skip_200_and_304,
        },
        'skip_boring_404s': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': zerver.lib.logging_util.skip_boring_404s,
        },
        'skip_site_packages_logs': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': zerver.lib.logging_util.skip_site_packages_logs,
        },
    },
    'handlers': {
        'zulip_admins': {
            'level': 'ERROR',
            'class': 'zerver.logging_handlers.AdminZulipHandler',
            # For testing the handler delete the next line
            'filters': ['ZulipLimiter', 'require_debug_false', 'require_really_deployed'],
            'formatter': 'default'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.WatchedFileHandler',
            'formatter': 'default',
            'filename': FILE_LOG_PATH,
        },
        'errors_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.WatchedFileHandler',
            'formatter': 'default',
            'filename': ERROR_FILE_LOG_PATH,
        },
    },
    'loggers': {
        '': {
            'handlers': DEFAULT_ZULIP_HANDLERS,
            'filters': ['require_logging_enabled'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': DEFAULT_ZULIP_HANDLERS,
            'level': 'INFO',
            'propagate': False,
        },
        'zulip.requests': {
            'handlers': DEFAULT_ZULIP_HANDLERS,
            'level': 'INFO',
            'propagate': False,
        },
        'zulip.queue': {
            'handlers': DEFAULT_ZULIP_HANDLERS,
            'level': 'WARNING',
            'propagate': False,
        },
        'zulip.management': {
            'handlers': ['file', 'errors_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'requests': {
            'handlers': DEFAULT_ZULIP_HANDLERS,
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security.DisallowedHost': {
            'handlers': ['file'],
            'propagate': False,
        },
        'django.request': {
            'handlers': DEFAULT_ZULIP_HANDLERS,
            'level': 'WARNING',
            'propagate': False,
            'filters': ['skip_boring_404s'],
        },
        'django.server': {
            'handlers': ['console', 'file'],
            'propagate': False,
            'filters': ['skip_200_and_304'],
        },
        'django.template': {
            'handlers': ['console'],
            'filters': ['require_debug_true', 'skip_site_packages_logs'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'zulip.zerver.webhooks': {
            'handlers': ['file', 'errors_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'zulip.soft_deactivation': {
            'handlers': ['file', 'errors_file'],
            'level': 'INFO',
            'propagate': False,
        }
        ## Uncomment the following to get all database queries logged to the console
        # 'django.db': {
        #     'handlers': ['console'],
        #     'level': 'DEBUG',
        #     'propagate': False,
        # },
    }
}

ACCOUNT_ACTIVATION_DAYS = 7

LOGIN_REDIRECT_URL = '/'

# Client-side polling timeout for get_events, in milliseconds.
# We configure this here so that the client test suite can override it.
# We already kill the connection server-side with heartbeat events,
# but it's good to have a safety.  This value should be greater than
# (HEARTBEAT_MIN_FREQ_SECS + 10)
POLL_TIMEOUT = 90 * 1000

# iOS App IDs
ZULIP_IOS_APP_ID = 'org.zulip.Zulip'

########################################################################
# SSO AND LDAP SETTINGS
########################################################################

USING_APACHE_SSO = ('zproject.backends.ZulipRemoteUserBackend' in AUTHENTICATION_BACKENDS)

if len(AUTHENTICATION_BACKENDS) == 1 and (AUTHENTICATION_BACKENDS[0] ==
                                          "zproject.backends.ZulipRemoteUserBackend"):
    HOME_NOT_LOGGED_IN = "/accounts/login/sso"
    ONLY_SSO = True
else:
    HOME_NOT_LOGGED_IN = '/login'
    ONLY_SSO = False
AUTHENTICATION_BACKENDS += ('zproject.backends.ZulipDummyBackend',)

# Redirect to /devlogin by default in dev mode
if DEVELOPMENT:
    HOME_NOT_LOGGED_IN = '/devlogin'
    LOGIN_URL = '/devlogin'

POPULATE_PROFILE_VIA_LDAP = bool(AUTH_LDAP_SERVER_URI)

if POPULATE_PROFILE_VIA_LDAP and \
   'zproject.backends.ZulipLDAPAuthBackend' not in AUTHENTICATION_BACKENDS:
    AUTHENTICATION_BACKENDS += ('zproject.backends.ZulipLDAPUserPopulator',)
else:
    POPULATE_PROFILE_VIA_LDAP = 'zproject.backends.ZulipLDAPAuthBackend' in AUTHENTICATION_BACKENDS or POPULATE_PROFILE_VIA_LDAP

########################################################################
# GITHUB AUTHENTICATION SETTINGS
########################################################################

# SOCIAL_AUTH_GITHUB_KEY is set in /etc/zulip/settings.py
SOCIAL_AUTH_GITHUB_SECRET = get_secret('social_auth_github_secret')
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login/'
SOCIAL_AUTH_GITHUB_SCOPE = ['user:email']
SOCIAL_AUTH_GITHUB_ORG_KEY = SOCIAL_AUTH_GITHUB_KEY
SOCIAL_AUTH_GITHUB_ORG_SECRET = SOCIAL_AUTH_GITHUB_SECRET
SOCIAL_AUTH_GITHUB_TEAM_KEY = SOCIAL_AUTH_GITHUB_KEY
SOCIAL_AUTH_GITHUB_TEAM_SECRET = SOCIAL_AUTH_GITHUB_SECRET

########################################################################
# EMAIL SETTINGS
########################################################################

# Django setting. Not used in the Zulip codebase.
DEFAULT_FROM_EMAIL = ZULIP_ADMINISTRATOR

if EMAIL_BACKEND is not None:
    # If the server admin specified a custom email backend, use that.
    pass
elif not EMAIL_HOST and PRODUCTION:
    # If an email host is not specified, fail silently and gracefully
    EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
elif DEVELOPMENT:
    # In the dev environment, emails are printed to the run-dev.py console.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST_PASSWORD = get_secret('email_password')
if EMAIL_GATEWAY_PASSWORD is None:
    EMAIL_GATEWAY_PASSWORD = get_secret('email_gateway_password')
if vars().get("AUTH_LDAP_BIND_PASSWORD") is None:
    AUTH_LDAP_BIND_PASSWORD = get_secret('auth_ldap_bind_password')

# Set the sender email address for Django traceback error reporting
if SERVER_EMAIL is None:
    SERVER_EMAIL = ZULIP_ADMINISTRATOR

########################################################################
# MISC SETTINGS
########################################################################

if PRODUCTION:
    # Filter out user data
    DEFAULT_EXCEPTION_REPORTER_FILTER = 'zerver.filters.ZulipExceptionReporterFilter'

# This is a debugging option only
PROFILE_ALL_REQUESTS = False

CROSS_REALM_BOT_EMAILS = set(('feedback@zulip.com', 'notification-bot@zulip.com', 'welcome-bot@zulip.com'))

CONTRIBUTORS_DATA = os.path.join(STATIC_ROOT, 'generated/github-contributors.json')
