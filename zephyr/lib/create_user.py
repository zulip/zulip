from django.conf import settings
from django.contrib.auth.models import UserManager
from django.utils import timezone
from zephyr.lib.initial_password import initial_api_key
from zephyr.models import UserProfile, Recipient, Subscription
import base64
import hashlib

# create_user_profile is based on Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
#
# Only use this for bulk_create -- for normal usage one should use
# create_user (below) which will also make the Subscription and
# Recipient objects
def create_user_profile(realm, email, password, active, full_name, short_name):
    now = timezone.now()
    email = UserManager.normalize_email(email)
    user_profile = UserProfile(email=email, is_staff=False, is_active=active,
                               full_name=full_name, short_name=short_name,
                               last_login=now, date_joined=now, realm=realm,
                               pointer=-1)

    if active:
        user_profile.set_password(password)
    else:
        user_profile.set_unusable_password()
    user_profile.api_key = initial_api_key(email)
    return user_profile

def create_user(email, password, realm, full_name, short_name,
                active=True):
    user_profile = create_user_profile(realm, email, password, active,
                                       full_name, short_name)
    user_profile.save()
    recipient = Recipient.objects.create(type_id=user_profile.id,
                                         type=Recipient.PERSONAL)
    Subscription.objects.create(user_profile=user_profile, recipient=recipient)
    return user_profile
