# Zulip Settings intended to be set by a system administrator.
#
# See http://zulip.readthedocs.io/en/latest/settings.html for
# detailed technical documentation on the Zulip settings system.
#
### MANDATORY SETTINGS
#
# These settings MUST be set in production. In a development environment,
# sensible default values will be used.

# The user-accessible Zulip hostname for this installation, e.g.
# zulip.example.com
EXTERNAL_HOST = 'zulip.example.com'

# The email address for the person or team who maintain the Zulip
# Voyager installation. Will also get support emails. (e.g. zulip-admin@example.com)
ZULIP_ADMINISTRATOR = 'zulip-admin@example.com'

# Enable at least one of the following authentication backends.
# See http://zulip.readthedocs.io/en/latest/prod-authentication-methods.html
# for documentation on our authentication backends.
AUTHENTICATION_BACKENDS = (
#    'zproject.backends.EmailAuthBackend', # Email and password; see SMTP setup below
#    'zproject.backends.GoogleMobileOauth2Backend', # Google Apps, setup below
#    'zproject.backends.GitHubAuthBackend', # GitHub auth, setup below
#    'zproject.backends.ZulipLDAPAuthBackend', # LDAP, setup below
#    'zproject.backends.ZulipRemoteUserBackend', # Local SSO, setup docs on readthedocs
    )

# To enable Google authentication, you need to do the following:
#
# (1) Visit https://console.developers.google.com, setup an
# Oauth2 client ID that allows redirects to
# e.g. https://zulip.example.com/accounts/login/google/done/.
#
# (2) Then click into the APIs and Auth section (in the sidebar on the
# left side of the page), APIs, then under "Social APIs" click on
# "Google+ API" and click the button to enable the API.
#
# (3) put your client secret as "google_oauth2_client_secret" in
# zulip-secrets.conf, and your client ID right here:
# GOOGLE_OAUTH2_CLIENT_ID=<your client ID from Google>


# To enable GitHub authentication, you will need to need to do the following:
#
# (1) Register an OAuth2 application with GitHub at one of:
#   https://github.com/settings/applications
#   https://github.com/organizations/ORGNAME/settings/applications
# Specify e.g. https://zulip.example.com/complete/github/ as the callback URL.
#
# (2) Put your "Client ID" as SOCIAL_AUTH_GITHUB_KEY below and your
# "Client secret" as social_auth_github_secret in
# /etc/zulip/zulip-secrets.conf.
# SOCIAL_AUTH_GITHUB_KEY = <your client ID from GitHub>
#
# (3) You can also configure the GitHub integration to only allow
# members of a particular GitHub team or organization to login to your
# Zulip server using GitHub authentication; to enable this, set one of the
# two parameters below:
# SOCIAL_AUTH_GITHUB_TEAM_ID = <your team id>
# SOCIAL_AUTH_GITHUB_ORG_NAME = <your org name>


# If you are using the ZulipRemoteUserBackend authentication backend,
# set this to your domain (e.g. if REMOTE_USER is "username" and the
# corresponding email address is "username@example.com", set
# SSO_APPEND_DOMAIN = "example.com")
SSO_APPEND_DOMAIN = None # type: str

# Configure the outgoing SMTP server below. For testing, you can skip
# sending emails entirely by commenting out EMAIL_HOST, but you will
# want to configure this to support email address confirmation emails,
# missed message emails, onboarding follow-up emails, etc. To
# configure SMTP, you will need to complete the following steps:
#
# (1) Fill out the outgoing email sending configuration below.
#
# (2) Put the SMTP password for EMAIL_HOST_USER in
# /etc/zulip/zulip-secrets.conf as email_password.
#
# (3) If you are using a gmail account to send outgoing email, you
# will likely need to read this Google support answer and configure
# that account as "less secure":
# https://support.google.com/mail/answer/14257.
#
# You can quickly test your sending email configuration using:
#   ./manage.py send_test_email username@example.com
#
# A common problem is hosting providers that block outgoing SMTP traffic.
#
# With the exception of reading EMAIL_HOST_PASSWORD from
# email_password in the Zulip secrets file, Zulip uses Django's
# standard EmailBackend, so if you're having issues, you may want to
# search for documentation on using your email provider with Django.
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = ''
EMAIL_PORT = 587
EMAIL_USE_TLS = True
# The email From address to be used for automatically generated emails
DEFAULT_FROM_EMAIL = "Zulip <zulip@example.com>"
# The noreply address to be used as Reply-To for certain generated emails.
# Messages sent to this address should not be delivered anywhere.
NOREPLY_EMAIL_ADDRESS = "noreply@example.com"

# A comma-separated list of strings representing the host/domain names
# that this Django site can serve. You should reset it to be a list of
# domains/IP addresses for your site. This is a security measure to
# prevent an attacker from poisoning caches and triggering password
# reset emails with links to malicious hosts by submitting requests
# with a fake HTTP Host header. See Django's documentation here:
# <https://docs.djangoproject.com/en/1.9/ref/settings/#allowed-hosts>.
# Zulip adds 'localhost' to the list automatically.
ALLOWED_HOSTS = ['*']

### OPTIONAL SETTINGS

# Controls whether session cookies expire when the browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Session cookie expiry in seconds after the last page load
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7 * 2 # 2 weeks

# Controls whether or not there is a feedback button in the UI.
ENABLE_FEEDBACK = False

# By default, the feedback button will submit feedback to the Zulip
# developers.  If you set FEEDBACK_EMAIL to be an email address
# (e.g. ZULIP_ADMINISTRATOR), feedback sent by your users will instead
# be sent to that email address.
FEEDBACK_EMAIL = ZULIP_ADMINISTRATOR

# Controls whether or not error reports are sent to Zulip.  Error
# reports are used to improve the quality of the product and do not
# include message contents; please contact Zulip support with any
# questions.
ERROR_REPORTING = True

# Controls whether or not Zulip will provide inline image preview when
# a link to an image is referenced in a message.
INLINE_IMAGE_PREVIEW = True

# By default, files uploaded by users and user avatars are stored
# directly on the Zulip server.  If file storage in Amazon S3 is
# desired, you can configure that as follows:
#
# (1) Set s3_key and s3_secret_key in /etc/zulip/zulip-secrets.conf to
# be the S3 access and secret keys that you want to use, and setting
# the S3_AUTH_UPLOADS_BUCKET and S3_AVATAR_BUCKET to be the S3 buckets
# you've created to store file uploads and user avatars, respectively.
# Then restart Zulip (scripts/restart-zulip).
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
# Different options are:
#   disable: I don't care about security, and I don't want to pay the overhead of encryption.
#   allow: I don't care about security, but I will pay the overhead of encryption if the server insists on it.
#   prefer: I don't care about encryption, but I wish to pay the overhead of encryption if the server supports it.
#   require: I want my data to be encrypted, and I accept the overhead. I trust that the network will make sure
#            I always connect to the server I want.
#   verify-ca: I want my data encrypted, and I accept the overhead. I want to be sure that I connect to a server
#              that I trust.
#   verify-full: I want my data encrypted, and I accept the overhead. I want to be sure that I connect to a server
#                I trust, and that it's the one I specify.
#REMOTE_POSTGRES_HOST = 'dbserver.example.com'
#REMOTE_POSTGRES_SSLMODE = 'require'

# If you want to set custom TOS, set the path to your markdown file, and uncomment
# the following line.
# TERMS_OF_SERVICE = '/etc/zulip/terms.md'

### TWITTER INTEGRATION

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

### EMAIL GATEWAY INTEGRATION

# The Email gateway integration supports sending messages into Zulip
# by sending an email.  This is useful for receiving notifications
# from third-party services that only send outgoing notifications via
# email.  Once this integration is configured, each stream will have
# an email address documented on the stream settings page an emails
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

### LDAP integration configuration
# Zulip supports retrieving information about users via LDAP, and
# optionally using LDAP as an authentication mechanism.
#
# In either configuration, you will need to do the following:
#
# * Fill in the LDAP configuration options below so that Zulip can
# connect to your LDAP server
#
# * Setup the mapping between email addresses (used as login names in
# Zulip) and LDAP usernames.  There are two supported ways to setup
# the username mapping:
#
#   (A) If users' email addresses are in LDAP, set
#       LDAP_APPEND_DOMAIN = None
#       AUTH_LDAP_USER_SEARCH to lookup users by email address
#
#   (B) If LDAP only has usernames but email addresses are of the form
#       username@example.com, you should set:
#       LDAP_APPEND_DOMAIN = example.com and
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
# binds are performed.  If set, you need to specify the password as
# 'auth_ldap_bind_password' in zulip-secrets.conf.
AUTH_LDAP_BIND_DN = ""

# Specify the search base and the property to filter on that corresponds to the
# username.
AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=example,dc=com",
    ldap.SCOPE_SUBTREE, "(uid=%(user)s)")

# If the value of a user's "uid" (or similar) property is not their email
# address, specify the domain to append here.
LDAP_APPEND_DOMAIN = None # type: str

# This map defines how to populate attributes of a Zulip user from LDAP.
AUTH_LDAP_USER_ATTR_MAP = {
# Populate the Django user's name from the LDAP directory.
    "full_name": "cn",
}

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
