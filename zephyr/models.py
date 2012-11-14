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
from django.db import transaction, IntegrityError
from zephyr.lib import bugdown
from zephyr.lib.bulk_create import batch_bulk_create
from zephyr.lib.avatar import gravatar_hash
import requests
from django.contrib.auth.models import UserManager
from django.utils import timezone
from django.contrib.sessions.models import Session
import time
import subprocess
import traceback
import re

@cache_with_key(lambda self: 'display_recipient_dict:%d' % (self.id,))
def get_display_recipient(recipient):
    """
    recipient: an instance of Recipient.

    returns: an appropriate string describing the recipient (the stream
    name, for a stream, or the email, for a user).
    """
    if recipient.type == Recipient.STREAM:
        stream = Stream.objects.get(id=recipient.type_id)
        return stream.name
    elif recipient.type == Recipient.HUDDLE:
        # We don't really care what the ordering is, just that it's deterministic.
        user_profile_list = (UserProfile.objects.filter(subscription__recipient=recipient)
                                                .select_related()
                                                .order_by('user__email'))
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
    recipient: an instance of Recipient.

    returns: an appropriate string describing the recipient (the stream
    name, for a stream, or the email, for a user).
    """
    if recipient.type == Recipient.STREAM:
        stream = Stream.objects.get(id=recipient.type_id)
        return stream.name

    user_profile_list = UserProfile.objects.filter(subscription__recipient=recipient).select_related()
    return [{'email': user_profile.user.email,
             'full_name': user_profile.full_name,
             'short_name': user_profile.short_name} for user_profile in user_profile_list]

class Callbacks(object):
    TYPE_RECEIVE = 0
    TYPE_POINTER_UPDATE = 1
    TYPE_MAX = 2

    def __init__(self):
        self.table = {}

    def add(self, key, cb_type, callback):
        if not self.table.has_key(key):
            self.create_key(key)
        self.table[key][cb_type].append(callback)

    def call(self, key, cb_type, **kwargs):
        if not self.table.has_key(key):
            self.create_key(key)

        for cb in self.table[key][cb_type]:
            cb(**kwargs)

        self.table[key][cb_type] = []

    def create_key(self, key):
        self.table[key] = [[] for i in range(0, Callbacks.TYPE_MAX)]


class Realm(models.Model):
    domain = models.CharField(max_length=40, db_index=True, unique=True)

    def __repr__(self):
        return "<Realm: %s %s>" % (self.domain, self.id)
    def __str__(self):
        return self.__repr__()

def bulk_create_realms(realm_list):
    existing_realms = set(r.domain for r in Realm.objects.select_related().all())

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

    # This is class data, not instance data!
    # There is one callbacks_table for the whole process.
    callbacks_table = Callbacks()

    # The user receives this message
    # Called in the Tornado process
    def receive(self, message):
        self.callbacks_table.call(self.user.id, Callbacks.TYPE_RECEIVE,
            messages=[message], update_types=["new_messages"])

    def update_pointer(self, new_pointer, pointer_updater):
        self.callbacks_table.call(self.user.id, Callbacks.TYPE_POINTER_UPDATE,
            new_pointer=new_pointer, pointer_updater=pointer_updater)

    def add_receive_callback(self, cb):
        self.callbacks_table.add(self.user.id, Callbacks.TYPE_RECEIVE, cb)

    def add_pointer_update_callback(self, cb):
        self.callbacks_table.add(self.user.id, Callbacks.TYPE_POINTER_UPDATE, cb)

    def __repr__(self):
        return "<UserProfile: %s %s>" % (self.user.email, self.realm)
    def __str__(self):
        return self.__repr__()

    @classmethod
    def create(cls, user, realm, full_name, short_name):
        """When creating a new user, make a profile for him or her."""
        if not cls.objects.filter(user=user):
            profile = cls(user=user, pointer=-1, realm=realm,
                          full_name=full_name, short_name=short_name)
            profile.api_key = initial_api_key(user.email)
            profile.save()
            # Auto-sub to the ability to receive personals.
            recipient = Recipient.objects.create(type_id=profile.id, type=Recipient.PERSONAL)
            Subscription.objects.create(user_profile=profile, recipient=recipient)
            return profile

class PreregistrationUser(models.Model):
    email = models.EmailField(unique=True)
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0)

class MitUser(models.Model):
    email = models.EmailField(unique=True)
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0)

# create_user_hack is the same as Django's User.objects.create_user,
# except that we don't save to the database so it can used in
# bulk_creates
def create_user_hack(username, password, email, active):
    now = timezone.now()
    email = UserManager.normalize_email(email)
    user = User(username=username, email=email,
                is_staff=False, is_active=active, is_superuser=False,
                last_login=now, date_joined=now)

    if active:
        user.set_password(password)
    else:
        user.set_unusable_password()
    return user

def create_user_base(email, password, active=True):
    # NB: the result of Base32 + truncation is not a valid Base32 encoding.
    # It's just a unique alphanumeric string.
    # Use base32 instead of base64 so we don't have to worry about mixed case.
    # Django imposes a limit of 30 characters on usernames.
    email_hash = hashlib.sha256(settings.HASH_SALT + email).digest()
    username = base64.b32encode(email_hash)[:30]
    return create_user_hack(username, password, email, active)

def create_user(email, password, realm, full_name, short_name,
                active=True):
    user = create_user_base(email=email, password=password,
                            active=active)
    user.save()
    return UserProfile.create(user, realm, full_name, short_name)

def compute_mit_user_fullname(email):
    try:
        # Input is either e.g. starnine@mit.edu or user|CROSSREALM.INVALID@mit.edu
        match_user = re.match(r'^([a-zA-Z0-9_.-]+)(\|.+)?@mit\.edu$', email.lower())
        if match_user and match_user.group(2) is None:
            dns_query = "%s.passwd.ns.athena.mit.edu" % (match_user.group(1),)
            proc = subprocess.Popen(['host', '-t', 'TXT', dns_query],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            out, _err_unused = proc.communicate()
            if proc.returncode == 0:
                # Parse e.g. 'starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash'
                # for the 4th passwd entry field, aka the person's name.
                return out.split(':')[4].split(',')[0]
        elif match_user:
            return match_user.group(1).lower() + "@" + match_user.group(2).upper()[1:]
    except:
        print ("Error getting fullname for %s:" % (email,))
        traceback.print_exc()
    return email.lower()

def create_mit_user_if_needed(realm, email):
    try:
        return UserProfile.objects.get(user__email=email)
    except UserProfile.DoesNotExist:
        try:
            # Forge a user for this person
            return create_user(email, initial_password(email), realm,
                               compute_mit_user_fullname(email), email.split("@")[0],
                               active=False)
        except IntegrityError:
            # Unless we raced with another thread doing the same
            # thing, in which case we should get the user they made
            transaction.commit()
            return UserProfile.objects.get(user__email=email)

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

def create_stream_if_needed(realm, stream_name):
    (stream, created) = Stream.objects.get_or_create(
        realm=realm, name__iexact=stream_name,
        defaults={'name': stream_name})
    if created:
        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
    return stream

def bulk_create_streams(realms, stream_list):
    existing_streams = set((stream.realm.domain, stream.name.lower())
                           for stream in Stream.objects.select_related().all())
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

    class Meta:
        unique_together = ("name", "realm")

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

    class Meta:
        unique_together = ("type", "type_id")

    # N.B. If we used Django's choice=... we would get this for free (kinda)
    _type_names = {
        PERSONAL: 'personal',
        STREAM:   'stream',
        HUDDLE:   'huddle' }

    def type_name(self):
        # Raises KeyError if invalid
        return self._type_names[self.type]

    def __repr__(self):
        display_recipient = get_display_recipient(self)
        return "<Recipient: %s (%d, %s)>" % (display_recipient, self.type_id, self.type)

class Client(models.Model):
    name = models.CharField(max_length=30, db_index=True, unique=True)

@transaction.commit_on_success
def get_client(name):
    try:
        (client, _) = Client.objects.get_or_create(name=name)
    except IntegrityError:
        # If we're racing with other threads trying to create this
        # client, get_or_create will throw IntegrityError (because our
        # database is enforcing the no-duplicate-objects constraint);
        # in this case one should just re-fetch the object.  This race
        # actually happens with populate_db.
        #
        # Much of the rest of our code that writes to the database
        # doesn't handle this duplicate object on race issue correctly :(
        transaction.commit()
        return Client.objects.get(name=name)
    return client

def bulk_create_clients(client_list):
    existing_clients = set(client.name for client in Client.objects.select_related().all())

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
        # Messages arrive in the Tornado process with the dicts already rendered.
        # This avoids running the Markdown parser and some database queries in the single-threaded
        # Tornado server.
        #
        # This field is not persisted to the database and will disappear if the object is re-fetched.
        if hasattr(self, 'precomputed_dicts'):
            return self.precomputed_dicts['text/html' if apply_markdown else 'text/x-markdown']

        obj = dict(
            id                = self.id,
            sender_email      = self.sender.user.email,
            sender_full_name  = self.sender.full_name,
            sender_short_name = self.sender.short_name,
            type              = self.recipient.type_name(),
            display_recipient = get_display_recipient(self.recipient),
            recipient_id      = self.recipient.id,
            subject           = self.subject,
            timestamp         = calendar.timegm(self.pub_date.timetuple()),
            gravatar_hash     = gravatar_hash(self.sender.user.email))

        if apply_markdown:
            obj['content'] = bugdown.convert(self.content)
            obj['content_type'] = 'text/html'
        else:
            obj['content'] = self.content
            obj['content_type'] = 'text/x-markdown'

        return obj

    def to_log_dict(self):
        return dict(
            id                = self.id,
            sender_email      = self.sender.user.email,
            sender_full_name  = self.sender.full_name,
            sender_short_name = self.sender.short_name,
            sending_client    = self.sending_client.name,
            type              = self.recipient.type_name(),
            recipient         = get_log_recipient(self.recipient),
            subject           = self.subject,
            content           = self.content,
            timestamp         = calendar.timegm(self.pub_date.timetuple()))

class UserMessage(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    message = models.ForeignKey(Message)
    # We're not using the archived field for now, but create it anyway
    # since this table will be an unpleasant one to do schema changes
    # on later
    archived = models.BooleanField()

    class Meta:
        unique_together = ("user_profile", "message")

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
    assert("timestamp" in event)
    if not os.path.exists(settings.MESSAGE_LOG + '.lock'):
        with open(settings.MESSAGE_LOG + '.lock', 'w') as lock:
            lock.write('0')

    with open(settings.MESSAGE_LOG + '.lock', 'r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with open(settings.MESSAGE_LOG, 'a') as log:
            log.write(simplejson.dumps(event) + '\n')
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
        raise ValueError('Bad recipient type')

    # Save the message receipts in the database
    # TODO: Use bulk_create here
    with transaction.commit_on_success():
        for user_profile in recipients:
            # Only deliver messages to "active" user accounts
            if user_profile.user.is_active:
                UserMessage(user_profile=user_profile, message=message).save()

    # We can only publish messages to longpolling clients if the Tornado server is running.
    if settings.TORNADO_SERVER:
        # Render Markdown etc. here, so that the single-threaded Tornado server doesn't have to.
        # TODO: Reduce duplication in what we send.
        rendered = { 'text/html':       message.to_dict(apply_markdown=True),
                     'text/x-markdown': message.to_dict(apply_markdown=False) }
        requests.post(settings.TORNADO_SERVER + '/notify_new_message', data=dict(
            secret   = settings.SHARED_SECRET,
            message  = message.id,
            rendered = simplejson.dumps(rendered),
            users    = ','.join(str(user.id) for user in recipients)))

class Subscription(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user_profile", "recipient")

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
                   'timestamp': time.time(),
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
                   'timestamp': time.time(),
                   'domain': stream.realm.domain})
    return did_remove

def do_activate_user(user, log=True):
    user.is_active = True
    user.set_password(initial_password(user.email))
    user.save()
    if log:
        log_event({'type': 'user_activated',
                   'timestamp': time.time(),
                   'user': user.email})

def do_change_password(user, password, log=True):
    user.set_password(password)
    user.save()
    if log:
        log_event({'type': 'user_change_password',
                   'timestamp': time.time(),
                   'user': user.email,
                   'pwhash': user.password})

def do_change_full_name(user_profile, full_name, log=True):
    user_profile.full_name = full_name
    user_profile.save()
    if log:
        log_event({'type': 'user_change_full_name',
                   'timestamp': time.time(),
                   'user': user_profile.user.email,
                   'full_name': full_name})

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

# This function is used only by tests.
# We have faster implementations within the app itself.
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

def clear_database():
    for model in [Message, Stream, UserProfile, User, Recipient,
                  Realm, Subscription, Huddle, UserMessage, Client]:
        model.objects.all().delete()
    Session.objects.all().delete()

class UserActivity(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    client = models.ForeignKey(Client)
    query = models.CharField(max_length=50, db_index=True)

    count = models.IntegerField()
    last_visit = models.DateTimeField('last visit')

    class Meta:
        unique_together = ("user_profile", "client", "query")
