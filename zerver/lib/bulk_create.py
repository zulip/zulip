from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Text

from zerver.lib.initial_password import initial_password
from zerver.models import Realm, Stream, UserProfile, Huddle, \
    Subscription, Recipient, Client, RealmAuditLog, get_huddle_hash
from zerver.lib.create_user import create_user_profile

def bulk_create_users(realm: Realm,
                      users_raw: Set[Tuple[Text, Text, Text, bool]],
                      bot_type: Optional[int]=None,
                      bot_owner: Optional[UserProfile]=None,
                      tos_version: Optional[Text]=None,
                      timezone: Text="") -> None:
    """
    Creates and saves a UserProfile with the given email.
    Has some code based off of UserManage.create_user, but doesn't .save()
    """
    existing_users = frozenset(UserProfile.objects.filter(
        realm=realm).values_list('email', flat=True))
    users = sorted([user_raw for user_raw in users_raw if user_raw[0] not in existing_users])

    # Now create user_profiles
    profiles_to_create = []  # type: List[UserProfile]
    for (email, full_name, short_name, active) in users:
        profile = create_user_profile(realm, email,
                                      initial_password(email), active, bot_type,
                                      full_name, short_name, bot_owner, False, tos_version,
                                      timezone, tutorial_status=UserProfile.TUTORIAL_FINISHED,
                                      enter_sends=True)
        profiles_to_create.append(profile)
    UserProfile.objects.bulk_create(profiles_to_create)

    RealmAuditLog.objects.bulk_create(
        [RealmAuditLog(realm=realm, modified_user=profile_,
                       event_type='user_created', event_time=profile_.date_joined)
         for profile_ in profiles_to_create])

    profiles_by_email = {}  # type: Dict[Text, UserProfile]
    profiles_by_id = {}  # type: Dict[int, UserProfile]
    for profile in UserProfile.objects.select_related().filter(realm=realm):
        profiles_by_email[profile.email] = profile
        profiles_by_id[profile.id] = profile

    recipients_to_create = []  # type: List[Recipient]
    for (email, full_name, short_name, active) in users:
        recipients_to_create.append(Recipient(type_id=profiles_by_email[email].id,
                                              type=Recipient.PERSONAL))
    Recipient.objects.bulk_create(recipients_to_create)

    recipients_by_email = {}  # type: Dict[Text, Recipient]
    for recipient in recipients_to_create:
        recipients_by_email[profiles_by_id[recipient.type_id].email] = recipient

    subscriptions_to_create = []  # type: List[Subscription]
    for (email, full_name, short_name, active) in users:
        subscriptions_to_create.append(
            Subscription(user_profile_id=profiles_by_email[email].id,
                         recipient=recipients_by_email[email]))
    Subscription.objects.bulk_create(subscriptions_to_create)

def bulk_create_streams(realm: Realm,
                        stream_dict: Dict[Text, Dict[Text, Any]]) -> None:
    existing_streams = frozenset([name.lower() for name in
                                  Stream.objects.filter(realm=realm)
                                  .values_list('name', flat=True)])
    streams_to_create = []  # type: List[Stream]
    for name, options in stream_dict.items():
        if name.lower() not in existing_streams:
            streams_to_create.append(
                Stream(
                    realm=realm, name=name, description=options["description"],
                    invite_only=options["invite_only"],
                    is_in_zephyr_realm=realm.is_zephyr_mirror_realm,
                )
            )
    # Sort streams by name before creating them so that we can have a
    # reliable ordering of `stream_id` across different python versions.
    # This is required for test fixtures which contain `stream_id`. Prior
    # to python 3.3 hashes were not randomized but after a security fix
    # hash randomization was enabled in python 3.3 which made iteration
    # of dictionaries and sets completely unpredictable. Here the order
    # of elements while iterating `stream_dict` will be completely random
    # for python 3.3 and later versions.
    streams_to_create.sort(key=lambda x: x.name)
    Stream.objects.bulk_create(streams_to_create)

    recipients_to_create = []  # type: List[Recipient]
    for stream in Stream.objects.filter(realm=realm).values('id', 'name'):
        if stream['name'].lower() not in existing_streams:
            recipients_to_create.append(Recipient(type_id=stream['id'],
                                                  type=Recipient.STREAM))
    Recipient.objects.bulk_create(recipients_to_create)
