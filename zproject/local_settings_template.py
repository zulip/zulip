# Template for Django settings for the Zulip local servers
import os
import platform
import re

# TODO: Rewrite this file to be more or less self-documenting as to
# how to generate each token securely and what other setup is needed.
# For now, we'll do that piecewise by component.

# Make this unique, and don't share it with anybody.
SECRET_KEY = ''

# A fixed salt used for hashing in certain places, e.g. email-based
# username generation.
HASH_SALT = ''

# Use this salt to hash a user's email into a filename for their user-uploaded
# avatar.  If this salt is discovered, attackers will only be able to determine
# that the owner of an email account has uploaded an avatar to Zulip, which isn't
# the end of the world.  Don't use the salt where there is more security exposure.
AVATAR_SALT = ''

# A shared secret, used to authenticate different parts of the app to each other.
SHARED_SECRET = ''

# Password for rabbitmq
RABBITMQ_PASSWORD = ''

# TODO: Make USING_MAILCHIMP do something (and default to False)
USING_MAILCHIMP = False

# This can be filled in automatically from the database
FEEDBACK_BOT_KEY = ''

# TODO: Make USING_MANDRILL do something (and default to False)
USING_MANDRILL = False

# This needs to be synced with the camo installation
CAMO_KEY = ''

# TODO: Put in example values
EMAIL_USE_TLS = True
EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT = 587

# Whether we're running in a production environment. Note that DEPLOYED does
# **not** mean hosted by us; customer sites are DEPLOYED and LOCALSERVER
# and as such should not for example assume they are the main Zulip site.
#
# TODO: Set these variables inside settings.py properly
DEPLOYED = os.path.exists('/etc/humbug-server')
STAGING_DEPLOYED = (platform.node() == 'staging.zulip.net')
TESTING_DEPLOYED = not not re.match(r'^test', platform.node())

LOCALSERVER = os.path.exists('/etc/zulip-local')

# TODO: Clean this up
if TESTING_DEPLOYED:
    EXTERNAL_HOST = platform.node()
elif STAGING_DEPLOYED:
    EXTERNAL_HOST = 'staging.zulip.com'
elif DEPLOYED:
    EXTERNAL_HOST = 'zulip.com'
else:
    EXTERNAL_HOST = 'localhost:9991'

# TODO: Replace these
S3_KEY=""
S3_SECRET_KEY=""
S3_BUCKET=""
S3_AVATAR_BUCKET=""

# TODO: Replace these
MIXPANEL_TOKEN = ""

# TODO: Add twitter template variables below.
