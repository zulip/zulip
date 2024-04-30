import os
from email.headerregistry import Address
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from django_auth_ldap.config import GroupOfUniqueNamesType, LDAPGroupType

from scripts.lib.zulip_tools import deport
from zproject.settings_types import JwtAuthKey, OIDCIdPConfigDict, SAMLIdPConfigDict

from .config import DEVELOPMENT, PRODUCTION, get_config, get_secret

if TYPE_CHECKING:
    from django_auth_ldap.config import LDAPSearch

if PRODUCTION:  # nocoverage
    from .prod_settings import EXTERNAL_HOST, ZULIP_ADMINISTRATOR
else:
    from .dev_settings import EXTERNAL_HOST, ZULIP_ADMINISTRATOR

DEBUG = DEVELOPMENT

EXTERNAL_HOST_WITHOUT_PORT = deport(EXTERNAL_HOST)

STATIC_URL: Optional[str] = None

# These settings are intended for the server admin to set.  We document them in
# prod_settings_template.py, and in the initial /etc/zulip/settings.py on a new
# install of the Zulip server.

# Extra HTTP "Host" values to allow (standard ones added in computed_settings.py)
ALLOWED_HOSTS: List[str] = []

# Basic email settings
NOREPLY_EMAIL_ADDRESS = Address(username="noreply", domain=EXTERNAL_HOST_WITHOUT_PORT).addr_spec
ADD_TOKENS_TO_NOREPLY_ADDRESS = True
TOKENIZED_NOREPLY_EMAIL_ADDRESS = Address(
    username="noreply-{token}", domain=EXTERNAL_HOST_WITHOUT_PORT
).addr_spec
PHYSICAL_ADDRESS = ""
FAKE_EMAIL_DOMAIN = EXTERNAL_HOST_WITHOUT_PORT

# SMTP settings
EMAIL_HOST: Optional[str] = None
# Other settings, like EMAIL_HOST_USER, EMAIL_PORT, and EMAIL_USE_TLS,
# we leave up to Django's defaults.

# LDAP auth
AUTH_LDAP_SERVER_URI = ""
AUTH_LDAP_BIND_DN = ""
AUTH_LDAP_USER_SEARCH: Optional["LDAPSearch"] = None
LDAP_APPEND_DOMAIN: Optional[str] = None
LDAP_EMAIL_ATTR: Optional[str] = None
AUTH_LDAP_REVERSE_EMAIL_SEARCH: Optional["LDAPSearch"] = None
AUTH_LDAP_USERNAME_ATTR: Optional[str] = None
# AUTH_LDAP_USER_ATTR_MAP is uncommented in prod_settings_template.py,
# so the value here mainly serves to help document the default.
AUTH_LDAP_USER_ATTR_MAP: Dict[str, str] = {
    "full_name": "cn",
}
# Automatically deactivate users not found by the AUTH_LDAP_USER_SEARCH query.
LDAP_DEACTIVATE_NON_MATCHING_USERS: Optional[bool] = None
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
AUTH_LDAP_ADVANCED_REALM_ACCESS_CONTROL: Optional[Dict[str, Any]] = None
LDAP_SYNCHRONIZED_GROUPS_BY_REALM: Dict[str, List[str]] = {}
AUTH_LDAP_GROUP_TYPE: LDAPGroupType = GroupOfUniqueNamesType()

# Social auth; we support providing values for some of these
# settings in zulip-secrets.conf instead of settings.py in development.
SOCIAL_AUTH_GITHUB_KEY = get_secret("social_auth_github_key", development_only=True)
SOCIAL_AUTH_GITHUB_ORG_NAME: Optional[str] = None
SOCIAL_AUTH_GITHUB_TEAM_ID: Optional[str] = None
SOCIAL_AUTH_GITLAB_KEY = get_secret("social_auth_gitlab_key", development_only=True)
SOCIAL_AUTH_SUBDOMAIN: Optional[str] = None
SOCIAL_AUTH_AZUREAD_OAUTH2_KEY = get_secret("social_auth_azuread_oauth2_key", development_only=True)
SOCIAL_AUTH_GOOGLE_KEY = get_secret("social_auth_google_key", development_only=True)
# SAML:
SOCIAL_AUTH_SAML_SP_ENTITY_ID: Optional[str] = None
SOCIAL_AUTH_SAML_SP_PUBLIC_CERT = ""
SOCIAL_AUTH_SAML_SP_PRIVATE_KEY = ""
SOCIAL_AUTH_SAML_ORG_INFO: Optional[Dict[str, Dict[str, str]]] = None
SOCIAL_AUTH_SAML_TECHNICAL_CONTACT: Optional[Dict[str, str]] = None
SOCIAL_AUTH_SAML_SUPPORT_CONTACT: Optional[Dict[str, str]] = None
SOCIAL_AUTH_SAML_ENABLED_IDPS: Dict[str, SAMLIdPConfigDict] = {}
SOCIAL_AUTH_SAML_SECURITY_CONFIG: Dict[str, Any] = {}
# Set this to True to enforce that any configured IdP needs to specify
# the limit_to_subdomains setting to be considered valid:
SAML_REQUIRE_LIMIT_TO_SUBDOMAINS = False

# Historical name for SOCIAL_AUTH_GITHUB_KEY; still allowed in production.
GOOGLE_OAUTH2_CLIENT_ID: Optional[str] = None

# Apple:
SOCIAL_AUTH_APPLE_SERVICES_ID = get_secret("social_auth_apple_services_id", development_only=True)
SOCIAL_AUTH_APPLE_APP_ID = get_secret("social_auth_apple_app_id", development_only=True)
SOCIAL_AUTH_APPLE_KEY = get_secret("social_auth_apple_key", development_only=True)
SOCIAL_AUTH_APPLE_TEAM = get_secret("social_auth_apple_team", development_only=True)
SOCIAL_AUTH_APPLE_SCOPE = ["name", "email"]
SOCIAL_AUTH_APPLE_EMAIL_AS_USERNAME = True

# Generic OpenID Connect:
SOCIAL_AUTH_OIDC_ENABLED_IDPS: Dict[str, OIDCIdPConfigDict] = {}
SOCIAL_AUTH_OIDC_FULL_NAME_VALIDATED = False

SOCIAL_AUTH_SYNC_CUSTOM_ATTRS_DICT: Dict[str, Dict[str, Dict[str, str]]] = {}

# Other auth
SSO_APPEND_DOMAIN: Optional[str] = None
CUSTOM_HOME_NOT_LOGGED_IN: Optional[str] = None

VIDEO_ZOOM_CLIENT_ID = get_secret("video_zoom_client_id", development_only=True)
VIDEO_ZOOM_CLIENT_SECRET = get_secret("video_zoom_client_secret")

# Email gateway
EMAIL_GATEWAY_PATTERN = ""
EMAIL_GATEWAY_LOGIN: Optional[str] = None
EMAIL_GATEWAY_IMAP_SERVER: Optional[str] = None
EMAIL_GATEWAY_IMAP_PORT: Optional[int] = None
EMAIL_GATEWAY_IMAP_FOLDER: Optional[str] = None
# Not documented for in /etc/zulip/settings.py, since it's rarely needed.
EMAIL_GATEWAY_EXTRA_PATTERN_HACK: Optional[str] = None

# Error reporting
ERROR_REPORTING = True
LOGGING_SHOW_MODULE = False
LOGGING_SHOW_PID = False

# Sentry.io error defaults to off
SENTRY_DSN: Optional[str] = get_config("sentry", "project_dsn", None)
SENTRY_TRACE_WORKER_RATE: Union[float, Dict[str, float]] = 0.0
SENTRY_TRACE_RATE: float = 0.0
SENTRY_PROFILE_RATE: float = 0.1
SENTRY_FRONTEND_DSN: Optional[str] = get_config("sentry", "frontend_project_dsn", None)
SENTRY_FRONTEND_SAMPLE_RATE: float = 1.0
SENTRY_FRONTEND_TRACE_RATE: float = 0.1

# File uploads and avatars
# TODO: Rename MAX_FILE_UPLOAD_SIZE to have unit in name.
DEFAULT_AVATAR_URI: Optional[str] = None
DEFAULT_LOGO_URI: Optional[str] = None
S3_AVATAR_BUCKET = ""
S3_AUTH_UPLOADS_BUCKET = ""
S3_REGION: Optional[str] = None
S3_ENDPOINT_URL: Optional[str] = None
S3_ADDRESSING_STYLE: Literal["auto", "virtual", "path"] = "auto"
S3_SKIP_PROXY = True
S3_UPLOADS_STORAGE_CLASS: Literal[
    "GLACIER_IR",
    "INTELLIGENT_TIERING",
    "ONEZONE_IA",
    "REDUCED_REDUNDANCY",
    "STANDARD",
    "STANDARD_IA",
] = "STANDARD"
LOCAL_UPLOADS_DIR: Optional[str] = None
LOCAL_AVATARS_DIR: Optional[str] = None
LOCAL_FILES_DIR: Optional[str] = None
MAX_FILE_UPLOAD_SIZE = 25
# How many GB an organization on a paid plan can upload per user,
# on zulipchat.com.
UPLOAD_QUOTA_PER_USER_GB = 5

# Jitsi Meet video call integration; set to None to disable integration.
JITSI_SERVER_URL: Optional[str] = "https://meet.jit.si"

# GIPHY API key.
GIPHY_API_KEY = get_secret("giphy_api_key")

# Allow setting BigBlueButton settings in zulip-secrets.conf in
# development; this is useful since there are no public BigBlueButton servers.
BIG_BLUE_BUTTON_URL = get_secret("big_blue_button_url", development_only=True)

# Max state storage per user
# TODO: Add this to zproject/prod_settings_template.py once stateful bots are fully functional.
USER_STATE_SIZE_LIMIT = 10000000
# Max size of a single configuration entry of an embedded bot.
BOT_CONFIG_SIZE_LIMIT = 10000

# External service configuration
CAMO_URI = ""
MEMCACHED_LOCATION = "127.0.0.1:11211"
MEMCACHED_USERNAME = None if get_secret("memcached_password") is None else "zulip@localhost"
RABBITMQ_HOST = "127.0.0.1"
RABBITMQ_PORT = 5672
RABBITMQ_USERNAME = "zulip"
RABBITMQ_USE_TLS = False
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REMOTE_POSTGRES_HOST = ""
REMOTE_POSTGRES_PORT = ""
REMOTE_POSTGRES_SSLMODE = ""
THUMBNAIL_IMAGES = False

TORNADO_PORTS: List[int] = []
USING_TORNADO = True

# ToS/Privacy templates
POLICIES_DIRECTORY: str = "zerver/policies_absent"

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
PROMOTE_SPONSORING_ZULIP = True
RATE_LIMITING = True
RATE_LIMITING_AUTHENTICATE = True
RATE_LIMIT_TOR_TOGETHER = False
SEND_LOGIN_EMAILS = True
EMBEDDED_BOTS_ENABLED = False

DEFAULT_RATE_LIMITING_RULES = {
    # Limits total number of API requests per unit time by each user.
    # Rate limiting general API access protects the server against
    # clients causing unreasonable server load.
    "api_by_user": [
        # 200 requests per minute
        (60, 200),
    ],
    # Limits total number of unauthenticated API requests (primarily
    # used by the public access option). Since these are
    # unauthenticated requests, each IP address is a separate bucket.
    "api_by_ip": [
        (60, 100),
    ],
    # Limits total requests to the Mobile Push Notifications Service
    # by each individual Zulip server that is using the service. This
    # is a Zulip Cloud setting that has no effect on self-hosted Zulip
    # servers that are not hosting their own copy of the push
    # notifications service.
    "api_by_remote_server": [
        (60, 1000),
    ],
    # Limits how many authentication attempts with login+password can
    # be made to a single username. This applies to the authentication
    # backends such as LDAP or email+password where a login+password
    # gets submitted to the Zulip server. No limit is applied for
    # external authentication methods (like GitHub SSO), since with
    # those authentication backends, we only receive a username if
    # authentication is successful.
    "authenticate_by_username": [
        # 5 failed login attempts within 30 minutes
        (1800, 5),
    ],
    # Limits how many requests a user can make to change their email
    # address. A low/strict limit is recommended here, since there is
    # not real use case for triggering several of these from a single
    # user account, and by definition, the emails are sent to an email
    # address that does not already have a relationship with Zulip, so
    # this feature can be abused to attack the server's spam
    # reputation. Applies in addition to sends_email_by_ip.
    "email_change_by_user": [
        # 2 emails per hour, and up to 5 per day.
        (3600, 2),
        (86400, 5),
    ],
    # Limits how many requests to send password reset emails can be
    # made for a single email address. A low/strict limit is
    # desirable, since this feature could be used to spam users with
    # password reset emails, given their email address. Applies in
    # addition to sends_email_by_ip, below.
    "password_reset_form_by_email": [
        # 2 emails per hour, and up to 5 per day.
        (3600, 2),
        (86400, 5),
    ],
    # This limit applies to all requests which directly trigger the
    # sending of an email, restricting the number per IP address. This
    # is a general anti-spam measure.
    "sends_email_by_ip": [
        (86400, 5),
    ],
    # Limits access to uploaded files, in web-public contexts, done by
    # unauthenticated users. Each file gets its own bucket, and every
    # access to the file by an unauthenticated user counts towards the
    # limit.  This is important to prevent abuse of Zulip's file
    # uploads feature for file distribution.
    "spectator_attachment_access_by_file": [
        # 1000 per day per file
        (86400, 1000),
    ],
    # A zilencer-only limit that applies to requests to the
    # remote billing system that trigger the sending of an email.
    "sends_email_by_remote_server": [
        # 10 emails per day
        (86400, 10),
    ],
}
# Rate limiting defaults can be individually overridden by adding
# entries in this object, which is merged with
# DEFAULT_RATE_LIMITING_RULES.
RATE_LIMITING_RULES: Dict[str, List[Tuple[int, int]]] = {}

# Two factor authentication is not yet implementation-complete
TWO_FACTOR_AUTHENTICATION_ENABLED = False

# This is used to send all hotspots for convenient manual testing
# in development mode.
ALWAYS_SEND_ALL_HOTSPOTS = False

# The new user tutorial is enabled by default, but can be disabled for
# self-hosters who want to disable the tutorial entirely on their system.
TUTORIAL_ENABLED = True

# We log emails in development environment for accessing
# them easily through /emails page
DEVELOPMENT_LOG_EMAILS = DEVELOPMENT

# The push bouncer expects to get its requests on the root subdomain,
# but that makes it more of a hassle to test bouncer endpoints in
# the development environment - so this setting allows us to disable
# that check.
DEVELOPMENT_DISABLE_PUSH_BOUNCER_DOMAIN_CHECK = False


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

NOTIFICATION_BOT = "notification-bot@zulip.com"
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"
NAGIOS_SEND_BOT = "nagios-send-bot@zulip.com"
NAGIOS_RECEIVE_BOT = "nagios-receive-bot@zulip.com"
WELCOME_BOT = "welcome-bot@zulip.com"
REMINDER_BOT = "reminder-bot@zulip.com"

# The following bots are optional system bots not enabled by
# default.  The default ones are defined in INTERNAL_BOTS, in settings.py.

# These are extra bot users for our end-to-end Nagios message
# sending tests.
NAGIOS_STAGING_SEND_BOT = "nagios-staging-send-bot@zulip.com" if PRODUCTION else None
NAGIOS_STAGING_RECEIVE_BOT = "nagios-staging-receive-bot@zulip.com" if PRODUCTION else None
# SYSTEM_BOT_REALM would be a constant always set to 'zulip',
# except that it isn't that on Zulip Cloud.  We will likely do a
# migration and eliminate this parameter in the future.
SYSTEM_BOT_REALM = "zulipinternal"

# Structurally, we will probably eventually merge
# analytics into part of the main server, rather
# than a separate app.
EXTRA_INSTALLED_APPS = ["analytics"]

# Used to construct URLs to point to the Zulip server.  Since we
# only support HTTPS in production, this is just for development.
EXTERNAL_URI_SCHEME = "https://"

# Whether anyone can create a new organization on the Zulip server.
OPEN_REALM_CREATION = False

# Whether it's possible to create web-public streams on this server.
WEB_PUBLIC_STREAMS_ENABLED = False

# Setting for where the system bot users are.  Likely has no
# purpose now that the REALMS_HAVE_SUBDOMAINS migration is finished.
SYSTEM_ONLY_REALMS = {"zulip"}

# Default deadline for demo organizations
DEMO_ORG_DEADLINE_DAYS = 30

# Alternate hostnames to serve particular realms on, in addition to
# their usual subdomains.  Keys are realm string_ids (aka subdomains),
# and values are alternate hosts.
# The values will also be added to ALLOWED_HOSTS.
REALM_HOSTS: Dict[str, str] = {}

# Map used to rewrite the URIs for certain realms during mobile
# authentication.  This, combined with adding the relevant hosts to
# ALLOWED_HOSTS, can be used for environments where security policies
# mean that a different hostname must be used for mobile access.
REALM_MOBILE_REMAP_URIS: Dict[str, str] = {}

# Whether the server is using the PGroonga full-text search
# backend.  Plan is to turn this on for everyone after further
# testing.
USING_PGROONGA = False

# How Django should send emails.  Set for most contexts in settings.py, but
# available for sysadmin override in unusual cases.
EMAIL_BACKEND: Optional[str] = None

# Whether to give admins a warning in the web app that email isn't set up.
# Set in settings.py when email isn't configured.
WARN_NO_EMAIL = False

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
APNS_TOKEN_KEY_FILE: Optional[str] = None
APNS_TOKEN_KEY_ID = get_secret("apns_token_key_id", development_only=True)
APNS_TEAM_ID = get_secret("apns_team_id", development_only=True)
APNS_SANDBOX = True
# APNS_TOPIC is obsolete. Clients now pass the APNs topic to use.
# ZULIP_IOS_APP_ID is obsolete. Clients now pass the iOS app ID to use for APNs.

# Limits related to the size of file uploads; last few in MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
MAX_AVATAR_FILE_SIZE_MIB = 5
MAX_ICON_FILE_SIZE_MIB = 5
MAX_LOGO_FILE_SIZE_MIB = 5
MAX_EMOJI_FILE_SIZE_MIB = 5

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

# What domains to treat like the root domain
ROOT_SUBDOMAIN_ALIASES = ["www"]
# Whether the root domain is a landing page or can host a realm.
ROOT_DOMAIN_LANDING_PAGE = False

# Subdomain for serving endpoints to users from self-hosted deployments.
SELF_HOSTING_MANAGEMENT_SUBDOMAIN: Optional[str] = None

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
TERMS_OF_SERVICE_VERSION: Optional[str] = None
# HTML template path (e.g. "corporate/zulipchat_migration_tos.html")
# displayed to users when increasing TERMS_OF_SERVICE_VERSION when a
# user is to accept the terms of service for the first time, but
# already has an account. This primarily comes up when doing a data
# import.
FIRST_TIME_TERMS_OF_SERVICE_TEMPLATE: Optional[str] = None
# Custom message (HTML allowed) to be displayed to explain why users
# need to re-accept the terms of service when a new major version is
# written.
TERMS_OF_SERVICE_MESSAGE: Optional[str] = None

# Configuration for JWT auth (sign in and API key fetch)
JWT_AUTH_KEYS: Dict[str, JwtAuthKey] = {}

# https://docs.djangoproject.com/en/3.2/ref/settings/#std:setting-SERVER_EMAIL
# Django setting for what from address to use in error emails.
SERVER_EMAIL = ZULIP_ADMINISTRATOR
# Django setting for who receives error emails.
ADMINS = (("Zulip Administrator", ZULIP_ADMINISTRATOR),)

# From address for welcome emails.
WELCOME_EMAIL_SENDER: Optional[Dict[str, str]] = None

# Whether to send periodic digests of activity.
SEND_DIGEST_EMAILS = True
# The variable part of email sender names to be used for outgoing emails.
INSTALLATION_NAME = EXTERNAL_HOST

# Used to change the Zulip logo in portico pages.
CUSTOM_LOGO_URL: Optional[str] = None

# Random salt used when deterministically generating passwords in
# development.
INITIAL_PASSWORD_SALT: Optional[str] = None

# Settings configuring the special instrumentation of the send_event
# code path used in generating API documentation for /events.
LOG_API_EVENT_TYPES = False

# Used to control whether certain management commands are run on
# the server.
# TODO: Replace this with a smarter "run on only one server" system.
STAGING = False

# Presence tuning parameters. These values were hardcoded in clients
# before Zulip 7.0 (feature level 164); modern clients should get them
# via the /register API response, making it possible to tune these to
# adjust the trade-off between freshness and presence-induced load.
#
# The default for OFFLINE_THRESHOLD_SECS is chosen as
# `PRESENCE_PING_INTERVAL_SECS * 3 + 20`, which is designed to allow 2
# round trips, plus an extra in case an update fails. See
# https://zulip.readthedocs.io/en/latest/subsystems/presence.html for
# details on the presence architecture.
#
# How long to wait before clients should treat a user as offline.
OFFLINE_THRESHOLD_SECS = 200
# How often a client should ping by asking for presence data of all users.
PRESENCE_PING_INTERVAL_SECS = 60
# Zulip sends immediate presence updates via the events system when a
# user joins or becomes online. In larger organizations, this can
# become prohibitively expensive, so we limit how many active users an
# organization can have before these presence update events are
# disabled.
USER_LIMIT_FOR_SENDING_PRESENCE_UPDATE_EVENTS = 100

# Controls the how much newer a user presence update needs to be
# than the currently saved last_active_time or last_connected_time in order for us to
# update the database state. E.g. If set to 0, we will do
# a database write each time a client sends a presence update.
PRESENCE_UPDATE_MIN_FREQ_SECONDS = 55

# Controls the timedelta between last_connected_time and last_active_time
# within which the user should be considered ACTIVE for the purposes of
# legacy presence events. That is - when sending a presence update about a user to clients,
# we will specify ACTIVE status  as long as the timedelta is within this limit and IDLE otherwise.
PRESENCE_LEGACY_EVENT_OFFSET_FOR_ACTIVITY_SECONDS = 70

# How many days deleted messages data should be kept before being
# permanently deleted.
ARCHIVED_DATA_VACUUMING_DELAY_DAYS = 30

# Enables billing pages and plan-based feature gates. If False, all features
# are available to all realms.
BILLING_ENABLED = False

CLOUD_FREE_TRIAL_DAYS: Optional[int] = int(get_secret("cloud_free_trial_days", "0"))
SELF_HOSTING_FREE_TRIAL_DAYS: Optional[int] = int(get_secret("self_hosting_free_trial_days", "30"))

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

# Used by puppet/kandra/files/cron.d/check_send_receive_time.
NAGIOS_BOT_HOST = EXTERNAL_HOST

# Use half of the available CPUs for data import purposes.
DEFAULT_DATA_EXPORT_IMPORT_PARALLELISM = (len(os.sched_getaffinity(0)) // 2) or 1

# How long after the last upgrade to nag users that the server needs
# to be upgraded because of likely security releases in the meantime.
# Default is 18 months, constructed as 12 months before someone should
# upgrade, plus 6 months for the system administrator to get around to it.
SERVER_UPGRADE_NAG_DEADLINE_DAYS = 30 * 18

# How long servers have to respond to outgoing webhook requests
OUTGOING_WEBHOOK_TIMEOUT_SECONDS = 10

# Maximum length of message content allowed.
# Any message content exceeding this limit will be truncated.
# See: `_internal_prep_message` function in zerver/actions/message_send.py.
MAX_MESSAGE_LENGTH = 10000

# The maximum number of drafts to send in the response to /register.
# More drafts, should they exist for some crazy reason, could be
# fetched in a separate request.
MAX_DRAFTS_IN_REGISTER_RESPONSE = 1000

# How long before a client should assume that another client sending
# typing notifications has gone away and expire the active typing
# indicator.
TYPING_STARTED_EXPIRY_PERIOD_MILLISECONDS = 45000

# How long after a user has stopped interacting with the compose UI
# that a client should send a stop notification to the server.
TYPING_STOPPED_WAIT_PERIOD_MILLISECONDS = 12000

# How often a client should send start notifications to the server to
# indicate that the user is still interacting with the compose UI.
TYPING_STARTED_WAIT_PERIOD_MILLISECONDS = 30000

# The maximum number of subscribers for a stream to have typing
# notifications enabled. Default is set to avoid excessive Tornado
# load in large organizations.
MAX_STREAM_SIZE_FOR_TYPING_NOTIFICATIONS = 100

# The maximum user-group size value upto which members should
# be soft-reactivated in the case of user group mention.
MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION = 11

# Limiting guest access to other users via the
# can_access_all_users_group setting makes presence queries much more
# expensive. This can be a significant performance problem for
# installations with thousands of users with many guests limited in
# this way, pending further optimization of the relevant code paths.
CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE = False

# General expiry time for signed tokens we may generate
# in some places through the codebase.
SIGNED_ACCESS_TOKEN_VALIDITY_IN_SECONDS = 60

CUSTOM_AUTHENTICATION_WRAPPER_FUNCTION: Optional[Callable[..., Any]] = None
