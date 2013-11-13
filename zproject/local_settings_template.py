# Template for Django settings for Zulip Enterprise

# This is the user-accessible Zulip hostname for this installation
EXTERNAL_HOST = ''

# This is the Zulip Administrator email address
ZULIP_ADMINISTRATOR = ''
ADMIN_DOMAIN = ''

# These credentials are for communication with the central Zulip deployment manager
DEPLOYMENT_ROLE_NAME = ''
DEPLOYMENT_ROLE_KEY = ''

# Configure the outgoing SMTP server below. For outgoing email
# via a GMail SMTP server, EMAIL_USE_TLS must be True and the
# outgoing port must be 587. The EMAIL_HOST is prepopulated
# for GMail servers, change it for other hosts, or leave it unset
# or empty to skip sending email.
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# Control whether or not there is a feedback button in the UI,
# which can be used to send feedback directly to Zulip
ENABLE_FEEDBACK = True

# By default uploaded files and avatars are stored directly on the Zulip server
# If file storage to Amazon S3 is desired, please contact Zulip Support
# (support@zulip.com) for further instructions on setting up S3 integration
LOCAL_UPLOADS_DIR = "/home/zulip/uploads"

# In order to show Tweet previews inline in messages, Zulip must have access
# to the Twitter API via OAuth. To fetch the various access tokens needed below,
# you must register a new application under your Twitter account by doing the following:
#
# 1. Log in to http://dev.twitter.com.
# 2. In the menu under your username, click My Applications. From this page, create a new application.
# 3. Click on the application you created and click "create my access token". Fill in the requested values.
TWITTER_CONSUMER_KEY = ''
TWITTER_CONSUMER_SECRET = ''
TWITTER_ACCESS_TOKEN_KEY = ''
TWITTER_ACCESS_TOKEN_SECRET = ''

# The email gateway provides an email address that you can use to post to a stream
# Emails received at the per-stream email address will be converted into a Zulip
# message

# The email address pattern to use for auto-generated stream emails
# The %s will be replaced with a unique token, and the resulting email
# must be delivered to the EMAIL_GATEWAY_IMAP_FOLDER of the EMAIL_GATEWAY_LOGIN account below
EMAIL_GATEWAY_PATTERN = ""

# The Zulip username of the bot that the email pattern should post as
EMAIL_GATEWAY_BOT = ""

# Configuration of the email mirror mailbox
# The IMAP login and password
EMAIL_GATEWAY_LOGIN = ""
EMAIL_GATEWAY_PASSWORD = ""
# The IMAP server & port to connect to
EMAIL_GATEWAY_IMAP_SERVER = ""
EMAIL_GATEWAY_IMAP_PORT = 993
# The IMAP folder name to check for emails. All emails sent to EMAIL_GATEWAY_PATTERN above
# must be delivered to this folder
EMAIL_GATEWAY_IMAP_FOLDER = "INBOX"

# When using SSO: If REMOTE_USER only provides a username, append this domain
# to the returned value.
SSO_APPEND_DOMAIN = None

# Enable at least one of the following authentication backends.
AUTHENTICATION_BACKENDS = (
#                           'zproject.backends.EmailAuthBackend', # Email and password
#                           'zerver.views.remote_user_sso', # Local SSO
#                           'zproject.backends.GoogleBackend', # Google Apps
    )

# Make session cookies expire when the browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Session cookie expiry in seconds after the last page load
SESSION_COOKIE_AGE = 1209600 # 2 weeks

# The following keys are automatically generated during the install process
# PLEASE DO NOT EDIT THEM
CAMO_KEY = ''
SECRET_KEY = ''
HASH_SALT = ''
RABBITMQ_PASSWORD = ''
AVATAR_SALT = ''
SHARED_SECRET = ''
