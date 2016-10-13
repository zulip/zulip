from __future__ import absolute_import

from django.contrib.auth.models import UserManager
from django.utils import timezone
from zerver.models import UserProfile, Recipient, Subscription, Realm, Stream
import base64
import ujson
import os
import string
from six.moves import range

from six import text_type
from typing import Optional

def random_api_key():
    # type: () -> text_type
    choices = string.ascii_letters + string.digits
    altchars = ''.join([choices[ord(os.urandom(1)) % 62] for _ in range(2)]).encode("utf-8")
    return base64.b64encode(os.urandom(24), altchars=altchars).decode("utf-8")

# create_user_profile is based on Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
#
# Only use this for bulk_create -- for normal usage one should use
# create_user (below) which will also make the Subscription and
# Recipient objects
def create_user_profile(realm, email, password, active, bot_type, full_name,
                        short_name, bot_owner, is_mirror_dummy, tos_version):
    # type: (Realm, text_type, text_type, bool, Optional[int], text_type, text_type, Optional[UserProfile], bool, Optional[text_type]) -> UserProfile
    now = timezone.now()
    email = UserManager.normalize_email(email)

    enable_stream_desktop_notifications = (realm.domain != 'zulip.com')

    user_profile = UserProfile(email=email, is_staff=False, is_active=active,
                               full_name=full_name, short_name=short_name,
                               last_login=now, date_joined=now, realm=realm,
                               pointer=-1, is_bot=bool(bot_type), bot_type=bot_type,
                               is_mirror_dummy=is_mirror_dummy,
                               tos_version=tos_version,
                               enable_stream_desktop_notifications=enable_stream_desktop_notifications,
                               onboarding_steps=ujson.dumps([]),
                               default_language=realm.default_language)
    if bot_owner is not None:
        # `user_profile.bot_owner = bot_owner` doesn't work on python 3.4
        user_profile.bot_owner_id = bot_owner.id

    if bot_type or not active:
        password = None

    user_profile.set_password(password)

    user_profile.api_key = random_api_key()
    return user_profile

def create_user(email, password, realm, full_name, short_name,
                active=True, bot_type=None, bot_owner=None, tos_version=None,
                avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
                is_mirror_dummy=False, default_sending_stream=None,
                default_events_register_stream=None,
                default_all_public_streams=None, user_profile_id=None):
    # type: (text_type, text_type, Realm, text_type, text_type, bool, Optional[int], Optional[UserProfile], Optional[text_type], text_type, bool, Optional[Stream], Optional[Stream], Optional[bool], Optional[int]) -> UserProfile
    user_profile = create_user_profile(realm, email, password, active, bot_type,
                                       full_name, short_name, bot_owner,
                                       is_mirror_dummy, tos_version)
    user_profile.avatar_source = avatar_source
    user_profile.default_sending_stream = default_sending_stream
    user_profile.default_events_register_stream = default_events_register_stream
    # Allow the ORM default to be used if not provided
    if default_all_public_streams is not None:
        user_profile.default_all_public_streams = default_all_public_streams

    if user_profile_id is not None:
        user_profile.id = user_profile_id

    user_profile.save()
    recipient = Recipient.objects.create(type_id=user_profile.id,
                                         type=Recipient.PERSONAL)
    Subscription.objects.create(user_profile=user_profile, recipient=recipient)
    return user_profile
