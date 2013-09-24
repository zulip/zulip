# Secret Django settings for the Zulip project
import os
import platform
import re

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# A fixed salt used for hashing in certain places, e.g. email-based
# username generation.
HASH_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Use this salt to hash a user's email into a filename for their user-uploaded
# avatar.  If this salt is discovered, attackers will only be able to determine
# that the owner of an email account has uploaded an avatar to Zulip, which isn't
# the end of the world.  Don't use the salt where there is more security exposure.
AVATAR_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Used just for generating initial passwords (only used in testing environments).
INITIAL_PASSWORD_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# A shared secret, used to authenticate different parts of the app to each other.
# FIXME: store this password more securely
SHARED_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# This password also appears in servers/configure-rabbitmq
RABBITMQ_PASSWORD = 'xxxxxxxxxxxxxxxx'

MAILCHIMP_API_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-us4'
ZULIP_FRIENDS_LIST_ID = '84b2f3da6b'

# This should be synced with our camo installation
CAMO_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

EMAIL_USE_TLS = True
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'humbug@humbughq.com'
EMAIL_HOST_PASSWORD = 'xxxxxxxxxxxxxxxx'
EMAIL_PORT = 587

DEPLOYED = (('zulip.net' in platform.node())
            or os.path.exists('/etc/humbug-server'))
STAGING_DEPLOYED = (platform.node() == 'staging.zulip.net')
TESTING_DEPLOYED = not not re.match(r'^test', platform.node())

EMBEDLY_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

if DEPLOYED:
    S3_KEY="xxxxxxxxxxxxxxxxxxxx"
    S3_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    S3_BUCKET="humbug-user-uploads"
    S3_AVATAR_BUCKET="humbug-user-avatars"

    MIXPANEL_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
else:
    S3_KEY="xxxxxxxxxxxxxxxxxxxx"
    S3_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    S3_BUCKET="humbug-user-uploads-test"
    S3_AVATAR_BUCKET="humbug-user-avatars-test"

    MIXPANEL_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
