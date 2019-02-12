from typing import Optional

################################################################
# Zulip Server settings.
#
# This file controls settings that affect the whole Zulip server.
# See our documentation at:
#   https://zulip.readthedocs.io/en/latest/production/settings.html
#
# For developer documentation on the Zulip settings system, see:
#   https://zulip.readthedocs.io/en/latest/subsystems/settings.html
#
# Remember to restart the server after making changes here!
#   su zulip -c /home/zulip/deployments/current/scripts/restart-server


################################
# Mandatory settings.
#
# These settings MUST be set in production. In a development environment,
# sensible default values will be used.

# The user-accessible Zulip hostname for this installation, e.g.
# zulip.example.com.  This should match what users will put in their
# web browser.  If you want to allow multiple hostnames, add the rest
# to ALLOWED_HOSTS.
#
# If you need to access the server on a specific port, you should set
# EXTERNAL_HOST to e.g. zulip.example.com:1234 here.
EXTERNAL_HOST = 'zulip.example.com'

# The email address for the person or team who maintains the Zulip
# installation. Note that this is a public-facing email address; it may
# appear on 404 pages, is used as the sender's address for many automated
# emails, and is advertised as a support address. An email address like
# support@example.com is totally reasonable, as is admin@example.com.
# Do not put a display name; e.g. 'support@example.com', not
# 'Zulip Support <support@example.com>'.
ZULIP_ADMINISTRATOR = 'zulip-admin@example.com'


################
# Outgoing email (SMTP) settings.
#
# Zulip needs to be able to send email (that is, use SMTP) so it can
# confirm new users' email addresses and send notifications.
#
# If you don't already have an SMTP provider, free ones are available.
#
# For more details, including a list of free SMTP providers and
# advice for troubleshooting, see the Zulip documentation:
#   https://zulip.readthedocs.io/en/latest/production/email.html

# EMAIL_HOST and EMAIL_HOST_USER are generally required.
#EMAIL_HOST = 'smtp.example.com'
#EMAIL_HOST_USER = ''

# Passwords and secrets are not stored in this file.  The password
# for user EMAIL_HOST_USER goes in `/etc/zulip/zulip-secrets.conf`.
# In that file, set `email_password`.  For example:
#   email_password = abcd1234

# EMAIL_USE_TLS and EMAIL_PORT are required for most SMTP providers.
#EMAIL_USE_TLS = True
#EMAIL_PORT = 587


################################
# Optional settings.

# The noreply address to be used as the sender for certain generated
# emails.  Messages sent to this address could contain sensitive user
# data and should not be delivered anywhere.  The default is
# e.g. noreply-{random_token}@zulip.example.com (if EXTERNAL_HOST is
# zulip.example.com).  There are potential security issues if you set
# ADD_TOKENS_TO_NOREPLY_ADDRESS=False to remove the token; see
# https://zulip.readthedocs.io/en/latest/production/email.html for details.
#ADD_TOKENS_TO_NOREPLY_ADDRESS = True
#TOKENIZED_NOREPLY_EMAIL_ADDRESS = "noreply-{token}@example.com"
# Used for noreply emails only if ADD_TOKENS_TO_NOREPLY_ADDRESS=False
#NOREPLY_EMAIL_ADDRESS = 'noreply@example.com'

# Many countries and bulk mailers require certain types of email to display
# a physical mailing address to comply with anti-spam legislation.
# Non-commercial and non-public-facing installations are unlikely to need
# this setting.
# The address should have no newlines.
#PHYSICAL_ADDRESS = ''

# A comma-separated list of strings representing the host/domain names
# that your users can enter in their browsers to access Zulip.
# This is a security measure; for details, see the Django documentation:
# https://docs.djangoproject.com/en/1.11/ref/settings/#allowed-hosts
#
# Zulip automatically adds to this list 'localhost', '127.0.0.1', and
# patterns representing EXTERNAL_HOST and subdomains of it.  If you are
# accessing your server by other hostnames, list them here.
#
# Note that these should just be hostnames, without port numbers.
#ALLOWED_HOSTS = ['zulip-alias.example.com', '192.0.2.1']


################
# Authentication settings.

# Enable at least one of the following authentication backends.
# See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html
# for documentation on our authentication backends.
#
# The install process requires EmailAuthBackend (the default) to be
# enabled.  If you want to disable it, do so after creating the
# initial realm and user.
AUTHENTICATION_BACKENDS = (
    'zproject.backends.EmailAuthBackend',  # Email and password; just requires SMTP setup
    # 'zproject.backends.GoogleMobileOauth2Backend',  # Google Apps, setup below
    # 'zproject.backends.GitHubAuthBackend',  # GitHub auth, setup below
    # 'zproject.backends.AzureADAuthBackend',  # Microsoft Azure Active Directory auth, setup below
    # 'zproject.backends.ZulipLDAPAuthBackend',  # LDAP, setup below
    # 'zproject.backends.ZulipRemoteUserBackend',  # Local SSO, setup docs on readthedocs
)

########
# Google OAuth.
#
# To set up Google authentication, you'll need to do the following:
#
# (1) Visit https://console.developers.google.com/ , navigate to
# "APIs & Services" > "Credentials", and create a "Project" which will
# correspond to your Zulip instance.
#
# (2) Navigate to "APIs & services" > "Library", and find the
# "Google+ API".  Choose "Enable".
#
# (3) Return to "Credentials", and select "Create credentials".
# Choose "OAuth client ID", and follow prompts to create a consent
# screen.  Fill in "Authorized redirect URIs" with a value like
#   https://zulip.example.com/accounts/login/google/done/
# based on your value for EXTERNAL_HOST.
#
# (4) You should get a client ID and a client secret. Copy them.
# Use the client ID as `GOOGLE_OAUTH2_CLIENT_ID` here, and put the
# client secret in zulip-secrets.conf as `google_oauth2_client_secret`.
#GOOGLE_OAUTH2_CLIENT_ID = <your client ID from Google>

########
# GitHub OAuth.
#
# To set up GitHub authentication, you'll need to do the following:
#
# (1) Register an OAuth2 application with GitHub at one of:
#   https://github.com/settings/developers
#   https://github.com/organizations/ORGNAME/settings/developers
# Fill in "Callback URL" with a value like
#   https://zulip.example.com/complete/github/ as
# based on your values for EXTERNAL_HOST and SOCIAL_AUTH_SUBDOMAIN.
#
# (2) You should get a page with settings for your new application,
# showing a client ID and a client secret.  Use the client ID as
# `SOCIAL_AUTH_GITHUB_KEY` here, and put the client secret in
# zulip-secrets.conf as `social_auth_github_secret`.
#SOCIAL_AUTH_GITHUB_KEY = <your client ID from GitHub>

# (3) Optionally, you can configure the GitHub integration to only
# allow members of a particular GitHub team or organization to log
# into your Zulip server through GitHub authentication.  To enable
# this, set one of the two parameters below:
#SOCIAL_AUTH_GITHUB_TEAM_ID = <your team id>
#SOCIAL_AUTH_GITHUB_ORG_NAME = <your org name>

# (4) If you are serving multiple Zulip organizations on different
# subdomains, you need to set SOCIAL_AUTH_SUBDOMAIN.  You can set it
# to any subdomain on which you do not plan to host a Zulip
# organization.  The default recommendation, `auth`, is a reserved
# subdomain; if you're using this setting, the "Callback URL" should be e.g.:
#   https://auth.zulip.example.com/complete/github/
#
# If you end up using a subdomain other then the default
# recommendation, you must also set the 'ROOT_SUBDOMAIN_ALIASES' list
# to include this subdomain.
#
#SOCIAL_AUTH_SUBDOMAIN = 'auth'


########
# Azure Active Directory OAuth.
#
# To set up Microsoft Azure AD authentication, you'll need to do the following:
#
# (1) Register an OAuth2 application with Microsoft at:
# https://apps.dev.microsoft.com
# Generate a new password under Application Secrets
# Generate a new platform (web) under Platforms. For Redirect URL, enter:
#   https://zulip.example.com/complete/azuread-oauth2/
# Add User.Read permission under Microsoft Graph Permissions
#
# (2) Enter the application ID for the app as SOCIAL_AUTH_AZUREAD_OAUTH2_KEY here
# (3) Put the application password in zulip-secrets.conf as 'azure_oauth2_secret'.
#SOCIAL_AUTH_AZUREAD_OAUTH2_KEY = ''

########
# SSO via REMOTE_USER.
#
# If you are using the ZulipRemoteUserBackend authentication backend,
# set this to your domain (e.g. if REMOTE_USER is "username" and the
# corresponding email address is "username@example.com", set
# SSO_APPEND_DOMAIN = "example.com")
SSO_APPEND_DOMAIN = None  # type: Optional[str]


################
# Miscellaneous settings.

# Support for mobile push notifications.  Setting controls whether
# push notifications will be forwarded through a Zulip push
# notification bouncer server to the mobile apps.  See
# https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html
# for information on how to sign up for and configure this.
#PUSH_NOTIFICATION_BOUNCER_URL = 'https://push.zulipchat.com'

# Whether to redact the content of push notifications.  This is less
# usable, but avoids sending message content over the wire.  In the
# future, we're likely to replace this with an end-to-end push
# notification encryption feature.
#PUSH_NOTIFICATION_REDACT_CONTENT = False

# Whether to submit basic usage statistics to help the Zulip core team.  Details at
#
#   https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html
#
# Defaults to True if and only if the Mobile Push Notifications Service is enabled.
#SUBMIT_USAGE_STATISTICS = True

# Controls whether session cookies expire when the browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Session cookie expiry in seconds after the last page load
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 2  # 2 weeks

# Password strength requirements; learn about configuration at
# https://zulip.readthedocs.io/en/latest/production/security-model.html.
# PASSWORD_MIN_LENGTH = 6
# PASSWORD_MIN_GUESSES = 10000

# Controls whether Zulip sends "new login" email notifications.
#SEND_LOGIN_EMAILS = True

# Controls whether or not there is a feedback button in the UI.
ENABLE_FEEDBACK = False

# Feedback sent by your users will be sent to this email address.
FEEDBACK_EMAIL = ZULIP_ADMINISTRATOR

# Controls whether or not error reports (tracebacks) are emailed to the
# server administrators.
#ERROR_REPORTING = True
# For frontend (JavaScript) tracebacks
#BROWSER_ERROR_REPORTING = False

# If True, each log message in the server logs will identify the
# Python module where it came from.  Useful for tracking down a
# mysterious log message, but a little verbose.
#LOGGING_SHOW_MODULE = False

# If True, each log message in the server logs will identify the
# process ID.  Useful for correlating logs with information from
# system-level monitoring tools.
#LOGGING_SHOW_PID = False

# Controls whether or not Zulip will provide inline image preview when
# a link to an image is referenced in a message.  Note: this feature
# can also be disabled in a realm's organization settings.
#INLINE_IMAGE_PREVIEW = True

# Controls whether or not Zulip will provide inline previews of
# websites that are referenced in links in messages.  Note: this feature
# can also be disabled in a realm's organization settings.
#INLINE_URL_EMBED_PREVIEW = False

# Controls whether or not Zulip will parse links starting with
# "file:///" as a hyperlink (useful if you have e.g. an NFS share).
ENABLE_FILE_LINKS = False

# By default, files uploaded by users and user avatars are stored
# directly on the Zulip server.  You can configure files being instead
# stored in Amazon S3 or another scalable data store here.  See docs at:
#
#   https://zulip.readthedocs.io/en/latest/production/upload-backends.html
LOCAL_UPLOADS_DIR = "/home/zulip/uploads"
#S3_AUTH_UPLOADS_BUCKET = ""
#S3_AVATAR_BUCKET = ""
#S3_REGION = ""

# Maximum allowed size of uploaded files, in megabytes.  DO NOT SET
# ABOVE 80MB.  The file upload implementation doesn't support chunked
# uploads, so browsers will crash if you try uploading larger files.
MAX_FILE_UPLOAD_SIZE = 25

# Controls whether name changes are completely disabled for this installation
# This is useful in settings where you're syncing names from an integrated LDAP/Active Directory
NAME_CHANGES_DISABLED = False

# Controls whether users who have not uploaded an avatar will receive an avatar
# from gravatar.com.
ENABLE_GRAVATAR = True

# To override the default avatar image if ENABLE_GRAVATAR is False, place your
# custom default avatar image at /home/zulip/local-static/default-avatar.png
# and uncomment the following line.
#DEFAULT_AVATAR_URI = '/local-static/default-avatar.png'

# To access an external postgres database you should define the host name in
# REMOTE_POSTGRES_HOST, you can define the password in the secrets file in the
# property postgres_password, and the SSL connection mode in REMOTE_POSTGRES_SSLMODE
# Valid values for REMOTE_POSTGRES_SSLMODE are documented in the
# "SSL Mode Descriptions" table in
#   https://www.postgresql.org/docs/9.5/static/libpq-ssl.html
#REMOTE_POSTGRES_HOST = 'dbserver.example.com'
#REMOTE_POSTGRES_SSLMODE = 'require'

# If you want to set a Terms of Service for your server, set the path
# to your markdown file, and uncomment the following line.
#TERMS_OF_SERVICE = '/etc/zulip/terms.md'

# Similarly if you want to set a Privacy Policy.
#PRIVACY_POLICY = '/etc/zulip/privacy.md'


################
# Twitter integration.

# Zulip supports showing inline Tweet previews when a tweet is linked
# to in a message.  To support this, Zulip must have access to the
# Twitter API via OAuth.  To obtain the various access tokens needed
# below, you must register a new application under your Twitter
# account by doing the following:
#
# 1. Log in to http://dev.twitter.com.
# 2. In the menu under your username, click My Applications. From this page, create a new application.
# 3. Click on the application you created and click "create my access token".
# 4. Fill in the values for twitter_consumer_key, twitter_consumer_secret, twitter_access_token_key,
#    and twitter_access_token_secret in /etc/zulip/zulip-secrets.conf.


################
# Email gateway integration.
#
# The Email gateway integration supports sending messages into Zulip
# by sending an email.  This is useful for receiving notifications
# from third-party services that only send outgoing notifications via
# email.  Once this integration is configured, each stream will have
# an email address documented on the stream settings page and emails
# sent to that address will be delivered into the stream.
#
# There are two ways to configure email mirroring in Zulip:
#  1. Local delivery: A MTA runs locally and passes mail directly to Zulip
#  2. Polling: Checks an IMAP inbox every minute for new messages.
#
# The local delivery configuration is preferred for production because
# it supports nicer looking email addresses and has no cron delay,
# while the polling mechanism is better for testing/developing this
# feature because it doesn't require a public-facing IP/DNS setup.
#
# The main email mirror setting is the email address pattern, where
# you specify the email address format you'd like the integration to
# use.  It should be one of the following:
#   %s@zulip.example.com (for local delivery)
#   username+%s@example.com (for polling if EMAIL_GATEWAY_LOGIN=username@example.com)
EMAIL_GATEWAY_PATTERN = ""
#
# If you are using local delivery, EMAIL_GATEWAY_PATTERN is all you need
# to change in this file.  You will also need to enable the Zulip postfix
# configuration to support local delivery by adding
#   , zulip::postfix_localmail
# to puppet_classes in /etc/zulip/zulip.conf and then running
# `scripts/zulip-puppet-apply -f` to do the installation.
#
# You will also need to setup DNS MX records to ensure emails sent to
# the hostname configured in EMAIL_GATEWAY_PATTERN will be delivered
# to the Zulip postfix server you installed above.
#
# If you are using polling, you will need to setup an IMAP email
# account dedicated to Zulip email gateway messages.  The model is
# that users will send emails to that account via an address of the
# form username+%s@example.com (which is what you will set as
# EMAIL_GATEWAY_PATTERN); your email provider should deliver those
# emails to the username@example.com inbox.  Then you run in a cron
# job `./manage.py email_mirror` (see puppet/zulip/files/cron.d/email-mirror),
# which will check that inbox and batch-process any new messages.
#
# You will need to configure authentication for the email mirror
# command to access the IMAP mailbox below and in zulip-secrets.conf.
#
# The IMAP login; username here and password as email_gateway_password in
# zulip-secrets.conf.
EMAIL_GATEWAY_LOGIN = ""
# The IMAP server & port to connect to
EMAIL_GATEWAY_IMAP_SERVER = ""
EMAIL_GATEWAY_IMAP_PORT = 993
# The IMAP folder name to check for emails. All emails sent to EMAIL_GATEWAY_PATTERN above
# must be delivered to this folder
EMAIL_GATEWAY_IMAP_FOLDER = "INBOX"


################
# LDAP integration.
#
# Zulip supports retrieving information about users via LDAP, and
# optionally using LDAP as an authentication mechanism.

import ldap
from django_auth_ldap.config import LDAPSearch

########
# LDAP integration, part 1: Connecting to the LDAP server.
#
# For detailed instructions, see the Zulip documentation:
#   https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap

# The LDAP server to connect to.  Setting this enables Zulip
# automatically fetching each new user's name from LDAP.
# Example: "ldaps://ldap.example.com"
AUTH_LDAP_SERVER_URI = ""

# The DN of the user to bind as (i.e., authenticate as) in order to
# query LDAP.  If unset, Zulip does an anonymous bind.
AUTH_LDAP_BIND_DN = ""

# Passwords and secrets are not stored in this file.  The password
# corresponding to AUTH_LDAP_BIND_DN goes in `/etc/zulip/zulip-secrets.conf`.
# In that file, set `auth_ldap_bind_password`.  For example:
#   auth_ldap_bind_password = abcd1234


########
# LDAP integration, part 2: Mapping user info from LDAP to Zulip.
#
# For detailed instructions, see the Zulip documentation:
#   https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap

# The LDAP search query to find a given user.
#
# The arguments to `LDAPSearch` are (base DN, scope, filter).  In the
# filter, the string `%(user)s` is a Python placeholder.  The Zulip
# server will replace this with the user's Zulip username, i.e. the
# name they type into the Zulip login form.
#
# For more details and alternatives, see the documentation linked above.
AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                   ldap.SCOPE_SUBTREE, "(uid=%(user)s)")

# Domain to combine with a user's username to figure out their email address.
#
# If users log in as e.g. "sam" when their email address is "sam@example.com",
# set this to "example.com".  If users log in with their full email addresses,
# leave as None; if the username -> email address mapping isn't so simple,
# leave as None and see LDAP_EMAIL_ATTR.
LDAP_APPEND_DOMAIN = None  # type: Optional[str]

# LDAP attribute to find a user's email address.
#
# Leave as None if users log in with their email addresses,
# or if using LDAP_APPEND_DOMAIN.
LDAP_EMAIL_ATTR = None  # type: Optional[str]

# This map defines how to populate attributes of a Zulip user from LDAP.
#
# The format is `zulip_name: ldap_name`; each entry maps a Zulip
# concept (on the left) to the LDAP attribute name (on the right) your
# LDAP database uses for the same concept.
AUTH_LDAP_USER_ATTR_MAP = {
    # full_name is required; common values include "cn" or "displayName".
    # If names are encoded in your LDAP directory as first and last
    # name, you can instead specify first_name and last_name, and
    # Zulip will combine those to construct a full_name automatically.
    "full_name": "cn",
    # "first_name": "fn",
    # "last_name": "ln",

    # User avatars can be pulled from the LDAP "thumbnailPhoto"/"jpegPhoto" field.
    # "avatar": "thumbnailPhoto",

    # This line is for having Zulip to automatically deactivate users
    # who are disabled in LDAP/Active Directory (and reactivate users who are not).
    # See docs for usage details and precise semantics.
    # "userAccountControl": "userAccountControl",
}

# Whether to automatically deactivate users not found in LDAP. If LDAP
# is the only authentication method, then this setting defaults to
# True.  If other authentication methods are enabled, it defaults to
# False.
#LDAP_DEACTIVATE_NON_MATCHING_USERS = True

################
# Miscellaneous settings.

# The default CAMO_URI of '/external_content/' is served by the camo
# setup in the default Voyager nginx configuration.  Setting CAMO_URI
# to '' will disable the Camo integration.
CAMO_URI = '/external_content/'

# RabbitMQ configuration
#
# By default, Zulip connects to rabbitmq running locally on the machine,
# but Zulip also supports connecting to RabbitMQ over the network;
# to use a remote RabbitMQ instance, set RABBITMQ_HOST here.
# RABBITMQ_HOST = "localhost"
# To use another rabbitmq user than the default 'zulip', set RABBITMQ_USERNAME here.
# RABBITMQ_USERNAME = 'zulip'

# Memcached configuration
#
# By default, Zulip connects to memcached running locally on the machine,
# but Zulip also supports connecting to memcached over the network;
# to use a remote Memcached instance, set MEMCACHED_LOCATION here.
# Format HOST:PORT
# MEMCACHED_LOCATION = 127.0.0.1:11211

# Redis configuration
#
# By default, Zulip connects to redis running locally on the machine,
# but Zulip also supports connecting to redis over the network;
# to use a remote Redis instance, set REDIS_HOST here.
# REDIS_HOST = '127.0.0.1'
# For a different redis port set the REDIS_PORT here.
# REDIS_PORT = 6379
# If you set redis_password in zulip-secrets.conf, Zulip will use that password
# to connect to the redis server.

# Controls whether Zulip will rate-limit user requests.
# RATE_LIMITING = True

# By default, Zulip connects to the thumbor (the thumbnailing software
# we use) service running locally on the machine.  If you're running
# thumbor on a different server, you can configure that by setting
# THUMBOR_URL here.  Setting THUMBOR_URL='' will let Zulip server know that
# thumbor is not running or configured.
#THUMBOR_URL = 'http://127.0.0.1:9995'
#
# This setting controls whether images shown in Zulip's inline image
# previews should be thumbnailed by thumbor, which saves bandwidth but
# can modify the image's appearance.
#THUMBNAIL_IMAGES = True

# Controls the Jitsi video call integration.  By default, the
# integration uses the SaaS meet.jit.si server.  You can specify
# your own Jitsi Meet server, or if you'd like to disable the
# integration, set JITSI_SERVER_URL = None.
#JITSI_SERVER_URL = 'jitsi.example.com'
