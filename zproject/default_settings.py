from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from django_auth_ldap.config import LDAPSearch
    from typing_extensions import TypedDict

from .config import DEVELOPMENT, PRODUCTION, get_secret

if PRODUCTION:
    from .prod_settings import EXTERNAL_HOST, ZULIP_ADMINISTRATOR
else:
    from .dev_settings import EXTERNAL_HOST, ZULIP_ADMINISTRATOR

DEBUG = DEVELOPMENT

# These settings are intended for the server admin to set.  We document them in
# prod_settings_template.py, and in the initial /etc/zulip/settings.py on a new
# install of the Zulip server.

# Extra HTTP "Host" values to allow (standard ones added in settings.py)
ALLOWED_HOSTS: List[str] = []

# Basic email settings
NOREPLY_EMAIL_ADDRESS = "noreply@" + EXTERNAL_HOST.split(":")[0]
ADD_TOKENS_TO_NOREPLY_ADDRESS = True
TOKENIZED_NOREPLY_EMAIL_ADDRESS = "noreply-{token}@" + EXTERNAL_HOST.split(":")[0]
PHYSICAL_ADDRESS = ''
FAKE_EMAIL_DOMAIN = EXTERNAL_HOST.split(":")[0]

# SMTP settings
EMAIL_HOST: Optional[str] = None
# Other settings, like EMAIL_HOST_USER, EMAIL_PORT, and EMAIL_USE_TLS,
# we leave up to Django's defaults.

# LDAP auth
AUTH_LDAP_SERVER_URI = ""
LDAP_EMAIL_ATTR: Optional[str] = None
AUTH_LDAP_USERNAME_ATTR: Optional[str] = None
AUTH_LDAP_REVERSE_EMAIL_SEARCH: Optional["LDAPSearch"] = None
# AUTH_LDAP_CONNECTION_OPTIONS: we set ldap.OPT_REFERRALS in settings.py if unset.
AUTH_LDAP_CONNECTION_OPTIONS: Dict[int, object] = {}
# Disable django-auth-ldap caching, to prevent problems with OU changes.
AUTH_LDAP_CACHE_TIMEOUT = 0
# Disable syncing user on each login; Using sync_ldap_user_data cron is recommended.
AUTH_LDAP_ALWAYS_UPDATE_USER = False
# Development-only settings for fake LDAP authentication; used to
# support local development of LDAP auth without an LDAP server.
# Detailed docs in zproject/dev_settings.py.
FAKE_LDAP_MODE: Optional[str] = None
FAKE_LDAP_NUM_USERS = 8

# Social auth; we support providing values for some of these
# settings in zulip-secrets.conf instead of settings.py in development.
SOCIAL_AUTH_GITHUB_KEY = get_secret('social_auth_github_key', development_only=True)
SOCIAL_AUTH_GITHUB_ORG_NAME: Optional[str] = None
SOCIAL_AUTH_GITHUB_TEAM_ID: Optional[str] = None
SOCIAL_AUTH_GITLAB_KEY = get_secret('social_auth_gitlab_key', development_only=True)
SOCIAL_AUTH_SUBDOMAIN: Optional[str] = None
SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET = get_secret('azure_oauth2_secret')
SOCIAL_AUTH_GOOGLE_KEY = get_secret('social_auth_google_key', development_only=True)
# SAML:
SOCIAL_AUTH_SAML_SP_ENTITY_ID: Optional[str] = None
SOCIAL_AUTH_SAML_SP_PUBLIC_CERT = ''
SOCIAL_AUTH_SAML_SP_PRIVATE_KEY = ''
SOCIAL_AUTH_SAML_ORG_INFO: Optional[Dict[str, Dict[str, str]]] = None
SOCIAL_AUTH_SAML_TECHNICAL_CONTACT: Optional[Dict[str, str]] = None
SOCIAL_AUTH_SAML_SUPPORT_CONTACT: Optional[Dict[str, str]] = None
SOCIAL_AUTH_SAML_ENABLED_IDPS: Dict[str, Dict[str, str]] = {}
SOCIAL_AUTH_SAML_SECURITY_CONFIG: Dict[str, Any] = {}
# Set this to True to enforce that any configured IdP needs to specify
# the limit_to_subdomains setting to be considered valid:
SAML_REQUIRE_LIMIT_TO_SUBDOMAINS = False
# Historical name for SOCIAL_AUTH_GITHUB_KEY; still allowed in production.
GOOGLE_OAUTH2_CLIENT_ID: Optional[str] = None

# Apple:
SOCIAL_AUTH_APPLE_SERVICES_ID = get_secret('social_auth_apple_services_id', development_only=True)
SOCIAL_AUTH_APPLE_BUNDLE_ID = get_secret('social_auth_apple_bundle_id', development_only=True)
SOCIAL_AUTH_APPLE_KEY = get_secret('social_auth_apple_key', development_only=True)
SOCIAL_AUTH_APPLE_TEAM = get_secret('social_auth_apple_team', development_only=True)
SOCIAL_AUTH_APPLE_SCOPE = ['name', 'email']
SOCIAL_AUTH_APPLE_EMAIL_AS_USERNAME = True

# Other auth
SSO_APPEND_DOMAIN: Optional[str] = None

VIDEO_ZOOM_CLIENT_ID = get_secret('video_zoom_client_id', development_only=True)
VIDEO_ZOOM_CLIENT_SECRET = get_secret('video_zoom_client_secret')

# Email gateway
EMAIL_GATEWAY_PATTERN = ''
EMAIL_GATEWAY_LOGIN: Optional[str] = None
EMAIL_GATEWAY_IMAP_SERVER: Optional[str] = None
EMAIL_GATEWAY_IMAP_PORT: Optional[int] = None
EMAIL_GATEWAY_IMAP_FOLDER: Optional[str] = None
# Not documented for in /etc/zulip/settings.py, since it's rarely needed.
EMAIL_GATEWAY_EXTRA_PATTERN_HACK: Optional[str] = None

# Error reporting
ERROR_REPORTING = True
BROWSER_ERROR_REPORTING = False
LOGGING_SHOW_MODULE = False
LOGGING_SHOW_PID = False

# File uploads and avatars
DEFAULT_AVATAR_URI = '/static/images/default-avatar.png'
DEFAULT_LOGO_URI = '/static/images/logo/zulip-org-logo.png'
S3_AVATAR_BUCKET = ''
S3_AUTH_UPLOADS_BUCKET = ''
S3_REGION = ''
LOCAL_UPLOADS_DIR: Optional[str] = None
MAX_FILE_UPLOAD_SIZE = 25

# Jitsi Meet video call integration; set to None to disable integration.
JITSI_SERVER_URL = 'https://meet.jit.si/'

# Max state storage per user
# TODO: Add this to zproject/prod_settings_template.py once stateful bots are fully functional.
USER_STATE_SIZE_LIMIT = 10000000
# Max size of a single configuration entry of an embedded bot.
BOT_CONFIG_SIZE_LIMIT = 10000

# External service configuration
CAMO_URI = ''
MEMCACHED_LOCATION = '127.0.0.1:11211'
MEMCACHED_USERNAME = None if get_secret("memcached_password") is None else "zulip@localhost"
RABBITMQ_HOST = '127.0.0.1'
RABBITMQ_USERNAME = 'zulip'
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REMOTE_POSTGRES_HOST = ''
REMOTE_POSTGRES_PORT = ''
REMOTE_POSTGRES_SSLMODE = ''
THUMBOR_URL = ''
THUMBOR_SERVES_CAMO = False
THUMBNAIL_IMAGES = False
SENDFILE_BACKEND: Optional[str] = None

# ToS/Privacy templates
PRIVACY_POLICY: Optional[str] = None
TERMS_OF_SERVICE: Optional[str] = None

# Security
ENABLE_FILE_LINKS = False
ENABLE_GRAVATAR = True
INLINE_IMAGE_PREVIEW = True
INLINE_URL_EMBED_PREVIEW = True
NAME_CHANGES_DISABLED = False
AVATAR_CHANGES_DISABLED = False
PASSWORD_MIN_LENGTH = 6
PASSWORD_MIN_GUESSES = 10000
PUSH_NOTIFICATION_BOUNCER_URL: Optional[str] = None
PUSH_NOTIFICATION_REDACT_CONTENT = False
SUBMIT_USAGE_STATISTICS = True
RATE_LIMITING = True
RATE_LIMITING_AUTHENTICATE = True
SEND_LOGIN_EMAILS = True
EMBEDDED_BOTS_ENABLED = False

# Two Factor Authentication is not yet implementation-complete
TWO_FACTOR_AUTHENTICATION_ENABLED = False

# This is used to send all hotspots for convenient manual testing
# in development mode.
ALWAYS_SEND_ALL_HOTSPOTS = False

# In-development search pills feature.
SEARCH_PILLS_ENABLED = False

# We log emails in development environment for accessing
# them easily through /emails page
DEVELOPMENT_LOG_EMAILS = DEVELOPMENT


# These settings are not documented in prod_settings_template.py.
# They should either be documented here, or documented there.
#
# Settings that it makes sense to document here instead of in
# prod_settings_template.py are those that
#  * don't make sense to change in production, but rather are intended
#    for dev and test environments; or
#  * don't make sense to change on a typical production server with
#    one or a handful of realms, though they might on an installation
#    like Zulip Cloud or to work around a problem on another server.

NOTIFICATION_BOT = 'notification-bot@zulip.com'
EMAIL_GATEWAY_BOT = 'emailgateway@zulip.com'
NAGIOS_SEND_BOT = 'nagios-send-bot@zulip.com'
NAGIOS_RECEIVE_BOT = 'nagios-receive-bot@zulip.com'
WELCOME_BOT = 'welcome-bot@zulip.com'
REMINDER_BOT = 'reminder-bot@zulip.com'

# The following bots are optional system bots not enabled by
# default.  The default ones are defined in INTERNAL_BOTS, in settings.py.

# ERROR_BOT sends Django exceptions to an "errors" stream in the
# system realm.
ERROR_BOT: Optional[str] = None
# These are extra bot users for our end-to-end Nagios message
# sending tests.
NAGIOS_STAGING_SEND_BOT = 'nagios-staging-send-bot@zulip.com' if PRODUCTION else None
NAGIOS_STAGING_RECEIVE_BOT = 'nagios-staging-receive-bot@zulip.com' if PRODUCTION else None
# SYSTEM_BOT_REALM would be a constant always set to 'zulip',
# except that it isn't that on Zulip Cloud.  We will likely do a
# migration and eliminate this parameter in the future.
SYSTEM_BOT_REALM = 'zulipinternal'

# Structurally, we will probably eventually merge
# analytics into part of the main server, rather
# than a separate app.
EXTRA_INSTALLED_APPS = ['analytics']

# Default GOOGLE_CLIENT_ID to the value needed for Android auth to work
GOOGLE_CLIENT_ID = '835904834568-77mtr5mtmpgspj9b051del9i9r5t4g4n.apps.googleusercontent.com'

# Legacy event logs configuration.  Our plans include removing
# log_event entirely in favor of RealmAuditLog, at which point we
# can remove this setting.
EVENT_LOGS_ENABLED = False

# Used to construct URLs to point to the Zulip server.  Since we
# only support HTTPS in production, this is just for development.
EXTERNAL_URI_SCHEME = "https://"

# Whether anyone can create a new organization on the Zulip server.
OPEN_REALM_CREATION = False

# Setting for where the system bot users are.  Likely has no
# purpose now that the REALMS_HAVE_SUBDOMAINS migration is finished.
SYSTEM_ONLY_REALMS = {"zulip"}

# Alternate hostnames to serve particular realms on, in addition to
# their usual subdomains.  Keys are realm string_ids (aka subdomains),
# and values are alternate hosts.
# The values will also be added to ALLOWED_HOSTS.
REALM_HOSTS: Dict[str, str] = {}

# Whether the server is using the Pgroonga full-text search
# backend.  Plan is to turn this on for everyone after further
# testing.
USING_PGROONGA = False

# How Django should send emails.  Set for most contexts in settings.py, but
# available for sysadmin override in unusual cases.
EMAIL_BACKEND: Optional[str] = None

# Whether to give admins a warning in the web app that email isn't set up.
# Set in settings.py when email isn't configured.
WARN_NO_EMAIL = False

# Whether to keep extra frontend stack trace data.
# TODO: Investigate whether this should be removed and set one way or other.
SAVE_FRONTEND_STACKTRACES = False

# If True, disable rate-limiting and other filters on sending error messages
# to admins, and enable logging on the error-reporting itself.  Useful
# mainly in development.
DEBUG_ERROR_REPORTING = False

# Whether to flush memcached after data migrations.  Because of
# how we do deployments in a way that avoids reusing memcached,
# this is disabled in production, but we need it in development.
POST_MIGRATION_CACHE_FLUSHING = False

# Settings for APNS.  Only needed on push.zulipchat.com or if
# rebuilding the mobile app with a different push notifications
# server.
APNS_CERT_FILE: Optional[str] = None
APNS_SANDBOX = True
APNS_TOPIC = 'org.zulip.Zulip'
ZULIP_IOS_APP_ID = 'org.zulip.Zulip'

# Max number of "remove notification" FCM/GCM messages to send separately
# in one burst; the rest are batched.  Older clients ignore the batched
# portion, so only receive this many removals.  Lower values mitigate
# server congestion and client battery use.  To batch unconditionally,
# set to 1.
MAX_UNBATCHED_REMOVE_NOTIFICATIONS = 10

# Limits related to the size of file uploads; last few in MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
MAX_AVATAR_FILE_SIZE = 5
MAX_ICON_FILE_SIZE = 5
MAX_LOGO_FILE_SIZE = 5
MAX_EMOJI_FILE_SIZE = 5

# Limits to help prevent spam, in particular by sending invitations.
#
# A non-admin user who's joined an open realm this recently can't invite at all.
INVITES_MIN_USER_AGE_DAYS = 3
# Default for a realm's `max_invites`; which applies per day,
# and only applies if OPEN_REALM_CREATION is true.
INVITES_DEFAULT_REALM_DAILY_MAX = 100
# Global rate-limit (list of pairs (days, max)) on invites from new realms.
# Only applies if OPEN_REALM_CREATION is true.
INVITES_NEW_REALM_LIMIT_DAYS = [(1, 100)]
# Definition of a new realm for INVITES_NEW_REALM_LIMIT.
INVITES_NEW_REALM_DAYS = 7

# Controls for which links are published in portico footers/headers/etc.
REGISTER_LINK_DISABLED: Optional[bool] = None
LOGIN_LINK_DISABLED = False
FIND_TEAM_LINK_DISABLED = True

# Controls if the server should run certain jobs like deliver_email or
# deliver_scheduled_messages. This setting in long term is meant for
# handling jobs for which we don't have a means of establishing a locking
# mechanism that works with multiple servers running these jobs.
# TODO: We should rename this setting so that it reflects its purpose actively.
EMAIL_DELIVERER_DISABLED = False

# What domains to treat like the root domain
# "auth" is by default a reserved subdomain for the use by python-social-auth.
ROOT_SUBDOMAIN_ALIASES = ["www", "auth"]
# Whether the root domain is a landing page or can host a realm.
ROOT_DOMAIN_LANDING_PAGE = False

# If using the Zephyr mirroring supervisord configuration, the
# hostname to connect to in order to transfer credentials from webathena.
PERSONAL_ZMIRROR_SERVER: Optional[str] = None

# When security-relevant links in emails expire.
CONFIRMATION_LINK_DEFAULT_VALIDITY_DAYS = 1
INVITATION_LINK_VALIDITY_DAYS = 10
REALM_CREATION_LINK_VALIDITY_DAYS = 7

# Version number for ToS.  Change this if you want to force every
# user to click through to re-accept terms of service before using
# Zulip again on the web.
TOS_VERSION: Optional[str] = None
# Template to use when bumping TOS_VERSION to explain situation.
FIRST_TIME_TOS_TEMPLATE: Optional[str] = None

# Hostname used for Zulip's statsd logging integration.
STATSD_HOST = ''

# Configuration for JWT auth.
if TYPE_CHECKING:
    class JwtAuthKey(TypedDict):
        key: str
        # See https://pyjwt.readthedocs.io/en/latest/algorithms.html for a list
        # of supported algorithms.
        algorithms: List[str]

JWT_AUTH_KEYS: Dict[str, "JwtAuthKey"] = {}

# https://docs.djangoproject.com/en/2.2/ref/settings/#std:setting-SERVER_EMAIL
# Django setting for what from address to use in error emails.
SERVER_EMAIL = ZULIP_ADMINISTRATOR
# Django setting for who receives error emails.
ADMINS = (("Zulip Administrator", ZULIP_ADMINISTRATOR),)

# From address for welcome emails.
WELCOME_EMAIL_SENDER: Optional[Dict[str, str]] = None
# Whether we should use users' own email addresses as the from
# address when sending missed-message emails.  Off by default
# because some transactional email providers reject sending such
# emails since they can look like spam.
SEND_MISSED_MESSAGE_EMAILS_AS_USER = False
# Whether to send periodic digests of activity.
SEND_DIGEST_EMAILS = True

# Used to change the Zulip logo in portico pages.
CUSTOM_LOGO_URL: Optional[str] = None

# Random salt used when deterministically generating passwords in
# development.
INITIAL_PASSWORD_SALT: Optional[str] = None

# Settings configuring the special instrumention of the send_event
# code path used in generating API documentation for /events.
LOG_API_EVENT_TYPES = False

# Used to control whether certain management commands are run on
# the server.
# TODO: Replace this with a smarter "run on only one server" system.
STAGING = False
# Configuration option for our email/Zulip error reporting.
STAGING_ERROR_NOTIFICATIONS = False

# How long to wait before presence should treat a user as offline.
# TODO: Figure out why this is different from the corresponding
# value in static/js/presence.js.  Also, probably move it out of
# default_settings, since it likely isn't usefully user-configurable.
OFFLINE_THRESHOLD_SECS = 5 * 60

# How many days deleted messages data should be kept before being
# permanently deleted.
ARCHIVED_DATA_VACUUMING_DELAY_DAYS = 7

# Enables billing pages and plan-based feature gates. If False, all features
# are available to all realms.
BILLING_ENABLED = False

FREE_TRIAL_DAYS = get_secret('free_trial_days', None)

# Custom message (supports HTML) to be shown in the navbar of landing pages. Used mainly for
# making announcements.
LANDING_PAGE_NAVBAR_MESSAGE: Optional[str] = None

# Automatically catch-up soft deactivated users when running the
# `soft-deactivate-users` cron. Turn this off if the server has 10Ks of
# users, and you would like to save some disk space. Soft-deactivated
# returning users would still be caught-up normally.
AUTO_CATCH_UP_SOFT_DEACTIVATED_USERS = True

# Enables Google Analytics on selected portico pages.
GOOGLE_ANALYTICS_ID: Optional[str] = None

# This is overridden by dev_settings.py for droplets.
IS_DEV_DROPLET = False

# Used by puppet/zulip_ops/files/cron.d/check_send_receive_time.
NAGIOS_BOT_HOST = EXTERNAL_HOST

# Automatically deactivate users not found by the AUTH_LDAP_USER_SEARCH query.
LDAP_DEACTIVATE_NON_MATCHING_USERS: Optional[bool] = None
