from __future__ import absolute_import
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Text

from zerver.lib.initial_password import initial_password
from zerver.models import Realm, Stream, UserProfile, Huddle, \
    Subscription, Recipient, Client, RealmAuditLog, get_huddle_hash
from zerver.lib.create_user import create_user_profile

def bulk_create_users(realm, users_raw, bot_type=None, tos_version=None):
    # type: (Realm, Set[Tuple[Text, Text, Text, bool]], Optional[int], Optional[Text]) -> None
    """
    Creates and saves a UserProfile with the given email.
    Has some code based off of UserManage.create_user, but doesn't .save()
    """
    existing_users = frozenset(UserProfile.objects.values_list('email', flat=True))
    users = sorted([user_raw for user_raw in users_raw if user_raw[0] not in existing_users])

    # Now create user_profiles
    profiles_to_create = [] # type: List[UserProfile]
    for (email, full_name, short_name, active) in users:
        profile = create_user_profile(realm, email,
                                      initial_password(email), active, bot_type,
                                      full_name, short_name, None, False, tos_version)
        profiles_to_create.append(profile)
    UserProfile.objects.bulk_create(profiles_to_create)

    RealmAuditLog.objects.bulk_create(
        [RealmAuditLog(realm=profile_.realm, modified_user=profile_,
                       event_type='user_created', event_time=profile_.date_joined)
         for profile_ in profiles_to_create])

    profiles_by_email = {} # type: Dict[Text, UserProfile]
    profiles_by_id = {} # type: Dict[int, UserProfile]
    for profile in UserProfile.objects.select_related().all():
        profiles_by_email[profile.email] = profile
        profiles_by_id[profile.id] = profile

    recipients_to_create = [] # type: List[Recipient]
    for (email, full_name, short_name, active) in users:
        recipients_to_create.append(Recipient(type_id=profiles_by_email[email].id,
                                              type=Recipient.PERSONAL))
    Recipient.objects.bulk_create(recipients_to_create)

    recipients_by_email = {} # type: Dict[Text, Recipient]
    for recipient in Recipient.objects.filter(type=Recipient.PERSONAL):
        recipients_by_email[profiles_by_id[recipient.type_id].email] = recipient

    subscriptions_to_create = [] # type: List[Subscription]
    for (email, full_name, short_name, active) in users:
        subscriptions_to_create.append(
            Subscription(user_profile_id=profiles_by_email[email].id,
                         recipient=recipients_by_email[email]))
    Subscription.objects.bulk_create(subscriptions_to_create)

def bulk_create_streams(realm, stream_dict):
    # type: (Realm, Dict[Text, Dict[Text, Any]]) -> None
    existing_streams = frozenset([name.lower() for name in
                                  Stream.objects.filter(realm=realm)
                                  .values_list('name', flat=True)])
    streams_to_create = [] # type: List[Stream]
    for name, options in stream_dict.items():
        if name.lower() not in existing_streams:
            streams_to_create.append(
                Stream(
                    realm=realm, name=name, description=options["description"],
                    invite_only=options["invite_only"]
                )
            )
    Stream.objects.bulk_create(streams_to_create)

    recipients_to_create = [] # type: List[Recipient]
    for stream in Stream.objects.filter(realm=realm).values('id', 'name'):
        if stream['name'].lower() not in existing_streams:
            recipients_to_create.append(Recipient(type_id=stream['id'],
                                                  type=Recipient.STREAM))
    Recipient.objects.bulk_create(recipients_to_create)

def bulk_create_clients(client_list):
    # type: (Iterable[Text]) -> None
    existing_clients = set(client.name for client in Client.objects.select_related().all()) # type: Set[Text]

    clients_to_create = [] # type: List[Client]
    for name in client_list:
        if name not in existing_clients:
            clients_to_create.append(Client(name=name))
            existing_clients.add(name)
    Client.objects.bulk_create(clients_to_create)

def bulk_create_huddles(users, huddle_user_list):
    # type: (Dict[Text, UserProfile], Iterable[Iterable[Text]]) -> None
    huddles = {} # type: Dict[Text, Huddle]
    huddles_by_id = {} # type: Dict[int, Huddle]
    huddle_set = set() # type: Set[Tuple[Text, Tuple[int, ...]]]
    existing_huddles = set() # type: Set[Text]
    for huddle in Huddle.objects.all():
        existing_huddles.add(huddle.huddle_hash)
    for huddle_users in huddle_user_list:
        user_ids = [users[email].id for email in huddle_users] # type: List[int]
        huddle_hash = get_huddle_hash(user_ids)
        if huddle_hash in existing_huddles:
            continue
        huddle_set.add((huddle_hash, tuple(sorted(user_ids))))

    huddles_to_create = [] # type: List[Huddle]
    for (huddle_hash, _) in huddle_set:
        huddles_to_create.append(Huddle(huddle_hash=huddle_hash))
    Huddle.objects.bulk_create(huddles_to_create)

    for huddle in Huddle.objects.all():
        huddles[huddle.huddle_hash] = huddle
        huddles_by_id[huddle.id] = huddle

    recipients_to_create = [] # type: List[Recipient]
    for (huddle_hash, _) in huddle_set:
        recipients_to_create.append(Recipient(type_id=huddles[huddle_hash].id, type=Recipient.HUDDLE))
    Recipient.objects.bulk_create(recipients_to_create)

    huddle_recipients = {} # type: Dict[Text, Recipient]
    for recipient in Recipient.objects.filter(type=Recipient.HUDDLE):
        huddle_recipients[huddles_by_id[recipient.type_id].huddle_hash] = recipient

    subscriptions_to_create = [] # type: List[Subscription]
    for (huddle_hash, huddle_user_ids) in huddle_set:
        for user_id in huddle_user_ids:
            subscriptions_to_create.append(Subscription(active=True, user_profile_id=user_id,
                                                        recipient=huddle_recipients[huddle_hash]))
    Subscription.objects.bulk_create(subscriptions_to_create)
