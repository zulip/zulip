from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
import hashlib
import base64
import calendar
from zephyr.lib.cache import cache_with_key
from zephyr.lib.initial_password import initial_password, initial_api_key
import fcntl
import os
import simplejson
from django.db import transaction
from zephyr.lib import bugdown
from zephyr.lib.bulk_create import batch_bulk_create
from zephyr.lib.avatar import gravatar_hash
import requests
from django.contrib.auth.models import UserManager
from django.utils import timezone

@cache_with_key(lambda self: 'display_recipient_dict:%d' % (self.id))
def get_display_recipient(recipient):
    """
    recipient: an subject of Recipient.

    returns: an appropriate string describing the recipient (the stream
    name, for a stream, or the email, for a user).
    """
    if recipient.type == Recipient.STREAM:
        stream = Stream.objects.get(id=recipient.type_id)
        return stream.name
    elif recipient.type == Recipient.HUDDLE:
        user_profile_list = [UserProfile.objects.select_related().get(user=s.user_profile) for s in
                             Subscription.objects.filter(recipient=recipient)]
        return [{'email': user_profile.user.email,
                 'full_name': user_profile.full_name,
                 'short_name': user_profile.short_name} for user_profile in user_profile_list]
    else:
        user_profile = UserProfile.objects.select_related().get(user=recipient.type_id)
        return {'email': user_profile.user.email,
                'full_name': user_profile.full_name,
                'short_name': user_profile.short_name}

def get_log_recipient(recipient):
    """
    recipient: an subject of Recipient.

    returns: an appropriate string describing the recipient (the stream
    name, for a stream, or the email, for a user).
    """
    if recipient.type == Recipient.STREAM:
        stream = Stream.objects.get(id=recipient.type_id)
        return stream.name

    user_profile_list = [UserProfile.objects.select_related().get(user=s.user_profile) for s in
                         Subscription.objects.filter(recipient=recipient)]
    return [{'email': user_profile.user.email,
             'full_name': user_profile.full_name,
             'short_name': user_profile.short_name} for user_profile in user_profile_list]

class Callbacks:
    TYPE_RECEIVE = 0
    TYPE_POINTER_UPDATE = 1
    TYPE_MAX = 2

    def __init__(self):
        self.table = {}

    def add(self, key, cb_type, callback):
        if not self.table.has_key(key):
            self.create_key(key)
        self.table[key][cb_type].append(callback)

    def get(self, key, cb_type):
        if not self.table.has_key(key):
            self.create_key(key)
        return self.table[key][cb_type]

    def clear(self, key, cb_type):
        if not self.table.has_key(key):
            self.create_key(key)
            return
        self.table[key][cb_type] = []

    def create_key(self, key):
        self.table[key] = [[] for i in range(0, Callbacks.TYPE_MAX)]

callbacks_table = Callbacks()

class Realm(models.Model):
    domain = models.CharField(max_length=40, db_index=True, unique=True)

    def __repr__(self):
        return "<Realm: %s %s>" % (self.domain, self.id)
    def __str__(self):
        return self.__repr__()

def bulk_create_realms(realm_list):
    existing_realms = set()
    for realm in Realm.objects.select_related().all():
        existing_realms.add(realm.domain)

    realms_to_create = []
    for domain in realm_list:
        if domain not in existing_realms:
            realms_to_create.append(Realm(domain=domain))
            existing_realms.add(domain)
    batch_bulk_create(Realm, realms_to_create)

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    full_name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=100)
    pointer = models.IntegerField()
    last_pointer_updater = models.CharField(max_length=64)
    realm = models.ForeignKey(Realm)
    api_key = models.CharField(max_length=32)

    # The user receives this message
    # Called in the Tornado process
    def receive(self, message):
        global callbacks_table

        for cb in callbacks_table.get(self.user.id, Callbacks.TYPE_RECEIVE):
            cb(messages=[message])

        callbacks_table.clear(self.user.id, Callbacks.TYPE_RECEIVE)

    def update_pointer(self, new_pointer, pointer_updater):
        global callbacks_table

        for cb in callbacks_table.get(self.user.id, Callbacks.TYPE_POINTER_UPDATE):
            cb(new_pointer=new_pointer, pointer_updater=pointer_updater)

        callbacks_table.clear(self.user.id, Callbacks.TYPE_POINTER_UPDATE)

    def add_receive_callback(self, cb):
        global callbacks_table
        callbacks_table.add(self.user.id, Callbacks.TYPE_RECEIVE, cb)

    def add_pointer_update_callback(self, cb):
        global callbacks_table
        callbacks_table.add(self.user.id, Callbacks.TYPE_POINTER_UPDATE, cb)

    def __repr__(self):
        return "<UserProfile: %s %s>" % (self.user.email, self.realm)
    def __str__(self):
        return self.__repr__()

    @classmethod
    def create(cls, user, realm, full_name, short_name):
        """When creating a new user, make a profile for him or her."""
        if not cls.objects.filter(user=user):
            profile = cls(user=user, pointer=-1, realm_id=realm.id,
                          full_name=full_name, short_name=short_name)
            profile.api_key = initial_api_key(user.email)
            profile.save()
            # Auto-sub to the ability to receive personals.
            recipient = Recipient.objects.create(type_id=profile.id, type=Recipient.PERSONAL)
            Subscription.objects.create(user_profile=profile, recipient=recipient)

class PreregistrationUser(models.Model):
    email = models.EmailField(unique=True)
    # 0 is inactive, 1 is active
    status = models.IntegerField(default=0)

# create_user_hack is the same as Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
def create_user_hack(username, password, email):
    now = timezone.now()
    email = UserManager.normalize_email(email)
    user = User(username=username, email=email,
                is_staff=False, is_active=True, is_superuser=False,
                last_login=now, date_joined=now)

    user.set_password(password)
    return user

def create_user_base(email, password):
    # NB: the result of Base32 + truncation is not a valid Base32 encoding.
    # It's just a unique alphanumeric string.
    # Use base32 instead of base64 so we don't have to worry about mixed case.
    # Django imposes a limit of 30 characters on usernames.
    email_hash = hashlib.sha256(settings.HASH_SALT + email).digest()
    username = base64.b32encode(email_hash)[:30]
    return create_user_hack(username, password, email)

def create_user(email, password, realm, full_name, short_name):
    user = create_user_base(email=email, password=password)
    user.save()
    return UserProfile.create(user, realm, full_name, short_name)

# TODO: This has a race where a user could be created twice.  Need to
# add transactions.
def create_user_if_needed(realm, email, full_name, short_name):
    try:
        return UserProfile.objects.get(user__email=email)
    except UserProfile.DoesNotExist:
        # forge a user for this person
        return create_user(email, initial_password(email), realm,
                           full_name, short_name)

def bulk_create_users(realms, users_raw):
    """
    Creates and saves a User with the given email.
    Has some code based off of UserManage.create_user, but doesn't .save()
    """
    users = []
    existing_users = set(u.email for u in User.objects.all())
    for (email, full_name, short_name) in users_raw:
        if email in existing_users:
            continue
        users.append((email, full_name, short_name))
        existing_users.add(email)

    users_to_create = []
    for (email, full_name, short_name) in users:
        users_to_create.append(create_user_base(email, initial_password(email)))
    batch_bulk_create(User, users_to_create, 30)

    users_by_email = {}
    for user in User.objects.all():
        users_by_email[user.email] = user

    # Now create user_profiles
    profiles_to_create = []
    for (email, full_name, short_name) in users:
        domain = email.split('@')[1]
        profile = UserProfile(user=users_by_email[email], pointer=-1,
                              realm_id=realms[domain].id,
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
    for (email, _, _) in users:
        recipients_to_create.append(Recipient(type_id=profiles_by_email[email].id,
                                              type=Recipient.PERSONAL))
    batch_bulk_create(Recipient, recipients_to_create)

    recipients_by_email = {}
    for recipient in Recipient.objects.filter(type=Recipient.PERSONAL):
        recipients_by_email[profiles_by_id[recipient.type_id].user.email] = recipient

    subscriptions_to_create = []
    for (email, _, _) in users:
        subscriptions_to_create.append(\
            Subscription(user_profile_id=profiles_by_email[email].id,
                         recipient=recipients_by_email[email]))
    batch_bulk_create(Subscription, subscriptions_to_create)

def create_stream_if_needed(realm, stream_name):
    (stream, created) = Stream.objects.get_or_create(
        realm=realm, name__iexact=stream_name,
        defaults={'name': stream_name})
    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
    return stream

def bulk_create_streams(realms, stream_list):
    existing_streams = set()
    for stream in Stream.objects.select_related().all():
        existing_streams.add((stream.realm.domain, stream.name.lower()))
    streams_to_create = []
    for (domain, name) in stream_list:
        if (domain, name.lower()) not in existing_streams:
            streams_to_create.append(Stream(realm=realms[domain], name=name))
    batch_bulk_create(Stream, streams_to_create)

    recipients_to_create = []
    for stream in Stream.objects.all():
        if (stream.realm.domain, stream.name.lower()) not in existing_streams:
            recipients_to_create.append(Recipient(type_id=stream.id,
                                                  type=Recipient.STREAM))
    batch_bulk_create(Recipient, recipients_to_create)

class Stream(models.Model):
    name = models.CharField(max_length=30, db_index=True)
    realm = models.ForeignKey(Realm, db_index=True)

    def __repr__(self):
        return "<Stream: %s>" % (self.name,)
    def __str__(self):
        return self.__repr__()

    @classmethod
    def create(cls, name, realm):
        stream = cls(name=name, realm=realm)
        stream.save()

        recipient = Recipient.objects.create(type_id=stream.id,
                                             type=Recipient.STREAM)
        return (stream, recipient)

class Recipient(models.Model):
    type_id = models.IntegerField(db_index=True)
    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, stream, huddle}
    PERSONAL = 1
    STREAM = 2
    HUDDLE = 3

    def type_name(self):
        if self.type == self.PERSONAL:
            return "personal"
        elif self.type == self.STREAM:
            return "stream"
        elif self.type == self.HUDDLE:
            return "huddle"
        else:
            raise

    def __repr__(self):
        display_recipient = get_display_recipient(self)
        return "<Recipient: %s (%d, %s)>" % (display_recipient, self.type_id, self.type)

class Client(models.Model):
    name = models.CharField(max_length=30, db_index=True, unique=True)

def get_client(name):
    (client, _) = Client.objects.get_or_create(name=name)
    return client

def bulk_create_clients(client_list):
    existing_clients = set()
    for client in Client.objects.select_related().all():
        existing_clients.add(client.name)

    clients_to_create = []
    for name in client_list:
        if name not in existing_clients:
            clients_to_create.append(Client(name=name))
            existing_clients.add(name)
    batch_bulk_create(Client, clients_to_create)

class Message(models.Model):
    sender = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    subject = models.CharField(max_length=60)
    content = models.TextField()
    pub_date = models.DateTimeField('date published')
    sending_client = models.ForeignKey(Client)

    def __repr__(self):
        display_recipient = get_display_recipient(self.recipient)
        return "<Message: %s / %s / %r>" % (display_recipient, self.subject, self.sender)
    def __str__(self):
        return self.__repr__()

    @cache_with_key(lambda self, apply_markdown: 'message_dict:%d:%d' % (self.id, apply_markdown))
    def to_dict(self, apply_markdown):
        if apply_markdown:
            content = bugdown.convert(self.content)
        else:
            content = self.content
        return {'id'               : self.id,
                'sender_email'     : self.sender.user.email,
                'sender_full_name' : self.sender.full_name,
                'sender_short_name': self.sender.short_name,
                'type'             : self.recipient.type_name(),
                'display_recipient': get_display_recipient(self.recipient),
                'recipient_id'     : self.recipient.id,
                'subject'          : self.subject,
                'content'          : content,
                'timestamp'        : calendar.timegm(self.pub_date.timetuple()),
                'gravatar_hash'    : gravatar_hash(self.sender.user.email),
                }

    def to_log_dict(self):
        return {'id'               : self.id,
                'sender_email'     : self.sender.user.email,
                'sender_full_name' : self.sender.full_name,
                'sender_short_name': self.sender.short_name,
                'sending_client'   : self.sending_client.name,
                'type'             : self.recipient.type_name(),
                'recipient'        : get_log_recipient(self.recipient),
                'subject'          : self.subject,
                'content'          : self.content,
                'timestamp'        : calendar.timegm(self.pub_date.timetuple()),
                }

class UserMessage(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    message = models.ForeignKey(Message)
    # We're not using the archived field for now, but create it anyway
    # since this table will be an unpleasant one to do schema changes
    # on later
    archived = models.BooleanField()

    def __repr__(self):
        display_recipient = get_display_recipient(self.message.recipient)
        return "<UserMessage: %s / %s>" % (display_recipient, self.user_profile.user.email)

user_hash = {}
def get_user_profile_by_id(uid):
    if uid in user_hash:
        return user_hash[uid]
    return UserProfile.objects.select_related().get(id=uid)

# Store an event in the log for re-importing messages
def log_event(event):
    if not os.path.exists(settings.MESSAGE_LOG + '.lock'):
        file(settings.MESSAGE_LOG + '.lock', "w").write("0")
    lock = open(settings.MESSAGE_LOG + '.lock', 'r')
    fcntl.flock(lock, fcntl.LOCK_EX)
    f = open(settings.MESSAGE_LOG, "a")
    f.write(simplejson.dumps(event) + "\n")
    f.flush()
    f.close()
    fcntl.flock(lock, fcntl.LOCK_UN)

def log_message(message):
    if not message.sending_client.name.startswith("test:"):
        log_event(message.to_log_dict())

def do_send_message(message, no_log=False):
    message.save()

    # Log the message to our message log for populate_db to refill
    if not no_log:
        log_message(message)

    if message.recipient.type == Recipient.PERSONAL:
        recipients = list(set([get_user_profile_by_id(message.recipient.type_id),
                               get_user_profile_by_id(message.sender_id)]))
        # For personals, you send out either 1 or 2 copies of the message, for
        # personals to yourself or to someone else, respectively.
        assert((len(recipients) == 1) or (len(recipients) == 2))
    elif (message.recipient.type == Recipient.STREAM or
          message.recipient.type == Recipient.HUDDLE):
        recipients = [s.user_profile for
                      s in Subscription.objects.select_related().filter(recipient=message.recipient, active=True)]
    else:
        raise

    # Save the message receipts in the database
    # TODO: Use bulk_create here
    with transaction.commit_on_success():
        for user_profile in recipients:
            UserMessage(user_profile=user_profile, message=message).save()

    # We can only publish messages to longpolling clients if the Tornado server is running.
    if settings.HAVE_TORNADO_SERVER:
        requests.post(settings.NOTIFY_NEW_MESSAGE_URL, data=[
               ('secret',  settings.SHARED_SECRET),
               ('message', message.id),
               ('users',   ','.join(str(user.id) for user in recipients))])

class Subscription(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    active = models.BooleanField(default=True)

    def __repr__(self):
        return "<Subscription: %r -> %r>" % (self.user_profile, self.recipient)
    def __str__(self):
        return self.__repr__()

def do_add_subscription(user_profile, stream, no_log=False):
    recipient = Recipient.objects.get(type_id=stream.id,
                                      type=Recipient.STREAM)
    (subscription, created) = Subscription.objects.get_or_create(
        user_profile=user_profile, recipient=recipient,
        defaults={'active': True})
    did_subscribe = created
    if not subscription.active:
        did_subscribe = True
        subscription.active = True
        subscription.save()
    if did_subscribe and not no_log:
        log_event({'type': 'subscription_added',
                   'user': user_profile.user.email,
                   'name': stream.name,
                   'domain': stream.realm.domain})
    return did_subscribe

def do_remove_subscription(user_profile, stream, no_log=False):
    recipient = Recipient.objects.get(type_id=stream.id,
                                      type=Recipient.STREAM)
    maybe_sub = Subscription.objects.filter(user_profile=user_profile,
                                    recipient=recipient)
    if len(maybe_sub) == 0:
        return False
    subscription = maybe_sub[0]
    did_remove = subscription.active
    subscription.active = False
    subscription.save()
    if did_remove and not no_log:
        log_event({'type': 'subscription_removed',
                   'user': user_profile.user.email,
                   'name': stream.name,
                   'domain': stream.realm.domain})
    return did_remove

class Huddle(models.Model):
    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)

def get_huddle_hash(id_list):
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return hashlib.sha1(hash_key).hexdigest()

def get_huddle(id_list):
    huddle_hash = get_huddle_hash(id_list)
    (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
    if created:
        recipient = Recipient.objects.create(type_id=huddle.id,
                                             type=Recipient.HUDDLE)
        # Add subscriptions
        for uid in id_list:
            Subscription.objects.create(recipient = recipient,
                                        user_profile = UserProfile.objects.get(id=uid))
    return huddle

def bulk_create_huddles(users, huddle_user_list):
    huddles = {}
    huddles_by_id = {}
    huddle_set = set()
    existing_huddles = {}
    for huddle in Huddle.objects.all():
        existing_huddles[huddle.huddle_hash] = True
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

# This is currently dead code since all the places where we used to
# use it now have faster implementations, but I expect this to be
# potentially useful for code in the future, so not deleting it yet.
def filter_by_subscriptions(messages, user):
    user_profile = UserProfile.objects.get(user=user)
    user_messages = []
    subscriptions = [sub.recipient for sub in
                     Subscription.objects.filter(user_profile=user_profile, active=True)]
    for message in messages:
        # If you are subscribed to the personal or stream, or if you
        # sent the personal, you can see the message.
        if (message.recipient in subscriptions) or \
                (message.recipient.type == Recipient.PERSONAL and
                 message.sender == user_profile):
            user_messages.append(message)

    return user_messages
