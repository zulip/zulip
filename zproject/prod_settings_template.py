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
# e.g. noreply@zulip.example.com (if EXTERNAL_HOST is
# zulip.example.com).
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
# based on your value for EXTERNAL_HOST.
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
# directly on the Zulip server.  If file storage in Amazon S3 is
# desired, you can configure that as follows:
#
# (1) Set s3_key and s3_secret_key in /etc/zulip/zulip-secrets.conf to
# be the S3 access and secret keys that you want to use, and setting
# the S3_AUTH_UPLOADS_BUCKET and S3_AVATAR_BUCKET to be the S3 buckets
# you've created to store file uploads and user avatars, respectively.
# Then restart Zulip (scripts/restart-server).
#
# (2) Edit /etc/nginx/sites-available/zulip-enterprise to comment out
# the nginx configuration for /user_uploads and /user_avatars (see
# https://github.com/zulip/zulip/issues/291 for discussion of a better
# solution that won't be automatically reverted by the Zulip upgrade
# script), and then restart nginx.
LOCAL_UPLOADS_DIR = "/home/zulip/uploads"
#S3_AUTH_UPLOADS_BUCKET = ""
#S3_AVATAR_BUCKET = ""

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
#
# In either configuration, you will need to do the following:
#
# * Fill in the LDAP configuration options below so that Zulip can
# connect to your LDAP server
#
# * Setup the mapping between LDAP attributes and Zulip.
# There are three supported ways to setup the username and/or email mapping:
#
#   (A) If users' email addresses are in LDAP and used as username, set
#       LDAP_APPEND_DOMAIN = None
#       AUTH_LDAP_USER_SEARCH to lookup users by email address
#
#   (B) If LDAP only has usernames but email addresses are of the form
#       username@example.com, you should set:
#       LDAP_APPEND_DOMAIN = example.com and
#       AUTH_LDAP_USER_SEARCH to lookup users by username
#
#   (C) If LDAP username are completely unrelated to email addresses,
#       you should set:
#       LDAP_EMAIL_ATTR = "email"
#       LDAP_APPEND_DOMAIN = None
#       AUTH_LDAP_USER_SEARCH to lookup users by username
#
# You can quickly test whether your configuration works by running:
#   ./manage.py query_ldap username@example.com
# From the root of your Zulip installation; if your configuration is working
# that will output the full name for your user.
#
# -------------------------------------------------------------
#
# If you are using LDAP for authentication, you will need to enable
# the zproject.backends.ZulipLDAPAuthBackend auth backend in
# AUTHENTICATION_BACKENDS above.  After doing so, you should be able
# to login to Zulip by entering your email address and LDAP password
# on the Zulip login form.
#
# If you are using LDAP to populate names in Zulip, once you finish
# configuring this integration, you will need to run:
#   ./manage.py sync_ldap_user_data
# To sync names for existing users; you may want to run this in a cron
# job to pick up name changes made on your LDAP server.
import ldap
from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

# URI of your LDAP server. If set, LDAP is used to prepopulate a user's name in
# Zulip. Example: "ldaps://ldap.example.com"
AUTH_LDAP_SERVER_URI = ""

# This DN will be used to bind to your server. If unset, anonymous
# binds are performed.
#
# If set, you need to specify the password in zulip-secrets.conf ,
# as 'auth_ldap_bind_password'.
AUTH_LDAP_BIND_DN = ""

# Specify the search base and the property to filter on that corresponds to the
# username.
AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
                                   ldap.SCOPE_SUBTREE, "(uid=%(user)s)")

# If the value of a user's "uid" (or similar) property is not their email
# address, specify the domain to append here.
LDAP_APPEND_DOMAIN = None  # type: Optional[str]

# If username and email are two different LDAP attributes, specify the
# attribute to get the user's email address from LDAP here.
LDAP_EMAIL_ATTR = None  # type: Optional[str]

# This map defines how to populate attributes of a Zulip user from LDAP.
AUTH_LDAP_USER_ATTR_MAP = {
    # full_name is required; common values include "cn" or "displayName".
    "full_name": "cn",
}


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

# Controls the Jitsi video call integration.  By default, the
# integration uses the SaaS meet.jit.si server.  You can specify
# your own Jitsi Meet server, or if you'd like to disable the
# integration, set JITSI_SERVER_URL = None.
#JITSI_SERVER_URL = 'jitsi.example.com'
