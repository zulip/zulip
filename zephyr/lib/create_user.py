from __future__ import absolute_import

from django.conf import settings
from django.contrib.auth.models import UserManager
from django.utils import timezone
from zephyr.lib.initial_password import initial_api_key
from zephyr.models import UserProfile, Recipient, Subscription
import base64
import hashlib
import simplejson

onboarding_steps = ["sent_stream_message", "sent_private_message", "made_app_sticky"]

def create_onboarding_steps_blob():
    return simplejson.dumps([(step, False) for step in onboarding_steps])

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

    user_profile.api_key = initial_api_key(email)
    return user_profile

def create_user(email, password, realm, full_name, short_name,
                active=True, bot=False, bot_owner=None):
    user_profile = create_user_profile(realm, email, password, active, bot,
                                       full_name, short_name, bot_owner)
    user_profile.save()
    recipient = Recipient.objects.create(type_id=user_profile.id,
                                         type=Recipient.PERSONAL)
    Subscription.objects.create(user_profile=user_profile, recipient=recipient)
    return user_profile
