from typing import Optional

import orjson
from django.contrib.auth.models import UserManager
from django.utils.timezone import now as timezone_now

from zerver.lib.hotspots import copy_hotpots
from zerver.lib.upload import copy_avatar
from zerver.lib.utils import generate_api_key
from zerver.models import (
    PreregistrationUser,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
    get_fake_email_domain,
)


def copy_user_settings(source_profile: UserProfile, target_profile: UserProfile) -> None:
    # Important note: Code run from here to configure the user's
    # settings should not call send_event, as that would cause clients
    # to throw an exception (we haven't sent the realm_user/add event
    # yet, so that event will include the updated details of target_profile).
    #
    # Note that this function will do at least one save() on target_profile.
    for settings_name in UserProfile.property_types:
        value = getattr(source_profile, settings_name)
        setattr(target_profile, settings_name, value)

    for settings_name in UserProfile.notification_setting_types:
        value = getattr(source_profile, settings_name)
        setattr(target_profile, settings_name, value)

    setattr(target_profile, "full_name", source_profile.full_name)
    setattr(target_profile, "enter_sends", source_profile.enter_sends)
    target_profile.save()

    if source_profile.avatar_source == UserProfile.AVATAR_FROM_USER:
        from zerver.lib.actions import do_change_avatar_fields
        do_change_avatar_fields(target_profile, UserProfile.AVATAR_FROM_USER,
                                skip_notify=True, acting_user=target_profile)
        copy_avatar(source_profile, target_profile)

    copy_hotpots(source_profile, target_profile)

def get_display_email_address(user_profile: UserProfile) -> str:
    if not user_profile.email_address_is_realm_public():
        return f"user{user_profile.id}@{get_fake_email_domain(user_profile.realm)}"
    return user_profile.delivery_email

def get_role_for_new_user(invited_as: int, realm_creation: bool=False) -> int:
    if realm_creation or invited_as == PreregistrationUser.INVITE_AS['REALM_OWNER']:
        return UserProfile.ROLE_REALM_OWNER
    elif invited_as == PreregistrationUser.INVITE_AS['REALM_ADMIN']:
        return UserProfile.ROLE_REALM_ADMINISTRATOR
    elif invited_as == PreregistrationUser.INVITE_AS['GUEST_USER']:
        return UserProfile.ROLE_GUEST
    return UserProfile.ROLE_MEMBER

# create_user_profile is based on Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
#
# Only use this for bulk_create -- for normal usage one should use
# create_user (below) which will also make the Subscription and
# Recipient objects
def create_user_profile(realm: Realm, email: str, password: Optional[str],
                        active: bool, bot_type: Optional[int], full_name: str,
                        bot_owner: Optional[UserProfile],
                        is_mirror_dummy: bool, tos_version: Optional[str],
                        timezone: Optional[str],
                        tutorial_status: str = UserProfile.TUTORIAL_WAITING,
                        enter_sends: bool = False,
                        force_id: Optional[int] = None) -> UserProfile:
    now = timezone_now()
    email = UserManager.normalize_email(email)

    extra_kwargs = {}
    if force_id is not None:
        extra_kwargs['id'] = force_id

    user_profile = UserProfile(is_staff=False, is_active=active,
                               full_name=full_name,
                               last_login=now, date_joined=now, realm=realm,
                               is_bot=bool(bot_type), bot_type=bot_type,
                               bot_owner=bot_owner, is_mirror_dummy=is_mirror_dummy,
                               tos_version=tos_version, timezone=timezone,
                               tutorial_status=tutorial_status,
                               enter_sends=enter_sends,
                               onboarding_steps=orjson.dumps([]).decode(),
                               default_language=realm.default_language,
                               twenty_four_hour_time=realm.default_twenty_four_hour_time,
                               delivery_email=email,
                               **extra_kwargs)
    if bot_type or not active:
        password = None
    if user_profile.email_address_is_realm_public():
        # If emails are visible to everyone, we can set this here and save a DB query
        user_profile.email = get_display_email_address(user_profile)
    user_profile.set_password(password)
    user_profile.api_key = generate_api_key()
    return user_profile

def create_user(email: str,
                password: Optional[str],
                realm: Realm,
                full_name: str,
                active: bool = True,
                role: Optional[int] = None,
                bot_type: Optional[int] = None,
                bot_owner: Optional[UserProfile] = None,
                tos_version: Optional[str] = None,
                timezone: str = "",
                avatar_source: str = UserProfile.AVATAR_FROM_GRAVATAR,
                is_mirror_dummy: bool = False,
                default_sending_stream: Optional[Stream] = None,
                default_events_register_stream: Optional[Stream] = None,
                default_all_public_streams: Optional[bool] = None,
                source_profile: Optional[UserProfile] = None,
                force_id: Optional[int] = None) -> UserProfile:
    user_profile = create_user_profile(
        realm,
        email,
        password,
        active,
        bot_type,
        full_name,
        bot_owner,
        is_mirror_dummy,
        tos_version,
        timezone,
        force_id=force_id
    )
    user_profile.avatar_source = avatar_source
    user_profile.timezone = timezone
    user_profile.default_sending_stream = default_sending_stream
    user_profile.default_events_register_stream = default_events_register_stream
    if role is not None:
        user_profile.role = role
    # Allow the ORM default to be used if not provided
    if default_all_public_streams is not None:
        user_profile.default_all_public_streams = default_all_public_streams
    # If a source profile was specified, we copy settings from that
    # user.  Note that this is positioned in a way that overrides
    # other arguments passed in, which is correct for most defaults
    # like timezone where the source profile likely has a better value
    # than the guess. As we decide on details like avatars and full
    # names for this feature, we may want to move it.
    if source_profile is not None:
        # copy_user_settings saves the attribute values so a secondary
        # save is not required.
        copy_user_settings(source_profile, user_profile)
    else:
        user_profile.save()

    if not user_profile.email_address_is_realm_public():
        # With restricted access to email addresses, we can't generate
        # the fake email addresses we use for display purposes without
        # a User ID, which isn't generated until the .save() above.
        user_profile.email = get_display_email_address(user_profile)
        user_profile.save(update_fields=['email'])

    recipient = Recipient.objects.create(type_id=user_profile.id,
                                         type=Recipient.PERSONAL)
    user_profile.recipient = recipient
    user_profile.save(update_fields=["recipient"])

    Subscription.objects.create(user_profile=user_profile, recipient=recipient)
    return user_profile
