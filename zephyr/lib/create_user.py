from __future__ import absolute_import

from django.contrib.auth.models import UserManager
from django.utils import timezone
from zephyr.models import UserProfile, Recipient, Subscription
import base64
import hashlib
import ujson
import random
import string

# The ordered list of onboarding steps we want new users to complete. If the
# steps are changed here, they must also be changed in onboarding.js.
onboarding_steps = ["sent_stream_message", "sent_private_message", "made_app_sticky"]

def create_onboarding_steps_blob():
    return ujson.dumps([(step, False) for step in onboarding_steps])

# create_user_profile is based on Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
#
# Only use this for bulk_create -- for normal usage one should use
# create_user (below) which will also make the Subscription and
# Recipient objects
def create_user_profile(realm, email, password, active, bot, full_name, short_name, bot_owner):
    now = timezone.now()
    email = UserManager.normalize_email(email)
    user_profile = UserProfile(email=email, is_staff=False, is_active=active,
                               full_name=full_name, short_name=short_name,
                               last_login=now, date_joined=now, realm=realm,
                               pointer=-1, is_bot=bot, bot_owner=bot_owner,
                               onboarding_steps=create_onboarding_steps_blob())

    if bot or not active:
        user_profile.set_unusable_password()
    else:
        user_profile.set_password(password)

    # select 2 random ascii letters or numbers to fill out our base 64 "encoding"
    randchars = random.choice(string.ascii_letters + string.digits) + \
        random.choice(string.ascii_letters + string.digits)
    # Generate a new, random API key
    user_profile.api_key = base64.b64encode(hashlib.sha256(str(random.getrandbits(256))).digest(),
                                   randchars)[0:32]
    return user_profile

def create_user(email, password, realm, full_name, short_name,
                active=True, bot=False, bot_owner=None,
                avatar_source=UserProfile.AVATAR_FROM_GRAVATAR):
    user_profile = create_user_profile(realm, email, password, active, bot,
                                       full_name, short_name, bot_owner)
    user_profile.avatar_source = avatar_source
    user_profile.save()
    recipient = Recipient.objects.create(type_id=user_profile.id,
                                         type=Recipient.PERSONAL)
    Subscription.objects.create(user_profile=user_profile, recipient=recipient)
    return user_profile
