from django.conf import settings

from zephyr.lib.initial_password import initial_password, initial_api_key
from zephyr.models import Realm, Stream, User, UserProfile, Huddle, \
    Subscription, Recipient, Client, Message, \
    get_huddle_hash
from zephyr.lib.actions import create_user_base

# batch_bulk_create should become obsolete with Django 1.5, when the
# Django bulk_create method accepts a batch_size directly.
def batch_bulk_create(cls, cls_list, batch_size=150):
    if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
        # We don't need a low batch size with mysql, but we do need
        # one to avoid "MySQL Server has gone away" errors
        batch_size = 10000
    while len(cls_list) > 0:
        current_batch = cls_list[0:batch_size]
        cls.objects.bulk_create(current_batch)
        cls_list = cls_list[batch_size:]

def bulk_create_realms(realm_list):
    existing_realms = set(r.domain for r in Realm.objects.select_related().all())

    realms_to_create = []
    for domain in realm_list:
        if domain not in existing_realms:
            realms_to_create.append(Realm(domain=domain))
            existing_realms.add(domain)
    batch_bulk_create(Realm, realms_to_create)

def bulk_create_users(realms, users_raw):
    """
    Creates and saves a User with the given email.
    Has some code based off of UserManage.create_user, but doesn't .save()
    """
    users = []
    existing_users = set(u.email for u in User.objects.all())
    for (email, full_name, short_name, active) in users_raw:
        if email in existing_users:
            continue
        users.append((email, full_name, short_name, active))
        existing_users.add(email)

    users_to_create = []
    for (email, full_name, short_name, active) in users:
        users_to_create.append(create_user_base(email, initial_password(email),
                                                active=active))
    batch_bulk_create(User, users_to_create, 30)

    users_by_email = {}
    for user in User.objects.all():
        users_by_email[user.email] = user

    # Now create user_profiles
    profiles_to_create = []
    for (email, full_name, short_name, active) in users:
        domain = email.split('@')[1]
        profile = UserProfile(user=users_by_email[email], pointer=-1,
                              realm=realms[domain],
                              full_name=full_name, short_name=short_name)
        profile.api_key = initial_api_key(email)
        profiles_to_create.append(profile)
    batch_bulk_create(UserProfile, profiles_to_create, 50)

    profiles_by_email = {}
    profiles_by_id = {}
    for profile in UserProfile.objects.select_related().all():
        profiles_by_email[profile.user.email] = profile
        profiles_by_id[profile.user.id] = profile

    recipients_to_create = []
    for (email, _, _, _) in users:
        recipients_to_create.append(Recipient(type_id=profiles_by_email[email].id,
                                              type=Recipient.PERSONAL))
    batch_bulk_create(Recipient, recipients_to_create)

    recipients_by_email = {}
    for recipient in Recipient.objects.filter(type=Recipient.PERSONAL):
        recipients_by_email[profiles_by_id[recipient.type_id].user.email] = recipient

    subscriptions_to_create = []
    for (email, _, _, _) in users:
        subscriptions_to_create.append(
            Subscription(user_profile_id=profiles_by_email[email].id,
                         recipient=recipients_by_email[email]))
    batch_bulk_create(Subscription, subscriptions_to_create)

def bulk_create_streams(realms, stream_list):
    existing_streams = set((stream.realm.domain, stream.name.lower())
                           for stream in Stream.objects.select_related().all())
    streams_to_create = []
    for (domain, name) in stream_list:
        if (domain, name.lower()) not in existing_streams:
            streams_to_create.append(Stream(realm=realms[domain], name=name))
    batch_bulk_create(Stream, streams_to_create)

    recipients_to_create = []
    for stream in Stream.objects.select_related().all():
        if (stream.realm.domain, stream.name.lower()) not in existing_streams:
            recipients_to_create.append(Recipient(type_id=stream.id,
                                                  type=Recipient.STREAM))
    batch_bulk_create(Recipient, recipients_to_create)

def bulk_create_clients(client_list):
    existing_clients = set(client.name for client in Client.objects.select_related().all())

    clients_to_create = []
    for name in client_list:
        if name not in existing_clients:
            clients_to_create.append(Client(name=name))
            existing_clients.add(name)
    batch_bulk_create(Client, clients_to_create)

def bulk_create_huddles(users, huddle_user_list):
    huddles = {}
    huddles_by_id = {}
    huddle_set = set()
    existing_huddles = set()
    for huddle in Huddle.objects.all():
        existing_huddles.add(huddle.huddle_hash)
    for huddle_users in huddle_user_list:
        user_ids = [users[email].id for email in huddle_users]
        huddle_hash = get_huddle_hash(user_ids)
        if huddle_hash in existing_huddles:
            continue
        huddle_set.add((huddle_hash, tuple(sorted(user_ids))))

    huddles_to_create = []
    for (huddle_hash, _) in huddle_set:
        huddles_to_create.append(Huddle(huddle_hash=huddle_hash))
    batch_bulk_create(Huddle, huddles_to_create)

    for huddle in Huddle.objects.all():
        huddles[huddle.huddle_hash] = huddle
        huddles_by_id[huddle.id] = huddle

    recipients_to_create = []
    for (huddle_hash, _) in huddle_set:
        recipients_to_create.append(Recipient(type_id=huddles[huddle_hash].id, type=Recipient.HUDDLE))
    batch_bulk_create(Recipient, recipients_to_create)

    huddle_recipients = {}
    for recipient in Recipient.objects.filter(type=Recipient.HUDDLE):
        huddle_recipients[huddles_by_id[recipient.type_id].huddle_hash] = recipient

    subscriptions_to_create = []
    for (huddle_hash, huddle_user_ids) in huddle_set:
        for user_id in huddle_user_ids:
            subscriptions_to_create.append(Subscription(active=True, user_profile_id=user_id,
                                                        recipient=huddle_recipients[huddle_hash]))
    batch_bulk_create(Subscription, subscriptions_to_create)
