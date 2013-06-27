from __future__ import absolute_import

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, UserManager
from zephyr.lib.cache import cache_with_key, update_user_profile_cache, \
    user_profile_by_id_cache_key, user_profile_by_email_cache_key, \
    update_user_presence_cache, generic_bulk_cached_fetch
from zephyr.lib.utils import make_safe_digest
from django.db import transaction, IntegrityError
from zephyr.lib import bugdown
from zephyr.lib.avatar import gravatar_hash, avatar_url
from django.utils import timezone
from django.contrib.sessions.models import Session
from zephyr.lib.timestamp import datetime_to_timestamp
from django.db.models.signals import post_save
import zlib

from bitfield import BitField
import ujson

MAX_SUBJECT_LENGTH = 60
MAX_MESSAGE_LENGTH = 10000

# Doing 1000 memcached requests to get_display_recipient is quite slow,
# so add a local cache as well as the memcached cache.
recipient_cache = {}
def get_display_recipient(recipient):
    if settings.TEST_SUITE:
        # The test suite expects all caching to be turned off
        return get_display_recipient_memcached(recipient)
    if recipient.id not in recipient_cache:
        recipient_cache[recipient.id] = get_display_recipient_memcached(recipient)
    return recipient_cache[recipient.id]

@cache_with_key(lambda self: 'display_recipient_dict:%d' % (self.id,),
                timeout=3600*24*7)
def get_display_recipient_memcached(recipient):
    """
    recipient: an instance of Recipient.

    returns: an appropriate object describing the recipient.  For a
    stream this will be the stream name as a string.  For a huddle or
    personal, it will be an array of dicts about each recipient.
    """
    if recipient.type == Recipient.STREAM:
        stream = Stream.objects.get(id=recipient.type_id)
        return stream.name

    # We don't really care what the ordering is, just that it's deterministic.
    user_profile_list = (UserProfile.objects.filter(subscription__recipient=recipient)
                                            .select_related()
                                            .order_by('email'))
    return [{'email': user_profile.email,
             'domain': user_profile.realm.domain,
             'full_name': user_profile.full_name,
             'short_name': user_profile.short_name} for user_profile in user_profile_list]

class Realm(models.Model):
    domain = models.CharField(max_length=40, db_index=True, unique=True)
    restricted_to_domain = models.BooleanField(default=True)

    def __repr__(self):
        return (u"<Realm: %s %s>" % (self.domain, self.id)).encode("utf-8")
    def __str__(self):
        return self.__repr__()

class UserProfile(AbstractBaseUser):
    # Fields from models.AbstractUser minus last_name and first_name,
    # which we don't use; email is modified to make it indexed and unique.
    email = models.EmailField(blank=False, db_index=True, unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_bot = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    bot_owner = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)

    USERNAME_FIELD = 'email'

    # Our custom site-specific fields
    full_name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=100)
    pointer = models.IntegerField()
    last_pointer_updater = models.CharField(max_length=64)
    realm = models.ForeignKey(Realm)
    api_key = models.CharField(max_length=32)
    enable_desktop_notifications = models.BooleanField(default=True)
    enable_sounds = models.BooleanField(default=True)
    enter_sends = models.NullBooleanField(default=False)
    enable_offline_email_notifications = models.BooleanField(default=True)
    last_reminder = models.DateTimeField(default=timezone.now, null=True)
    rate_limits = models.CharField(default="", max_length=100) # comma-separated list of range:max pairs

    # Hours to wait before sending another email to a user
    EMAIL_REMINDER_WAITPERIOD = 24

    AVATAR_FROM_GRAVATAR = 'G'
    AVATAR_FROM_USER = 'U'
    AVATAR_FROM_SYSTEM = 'S'
    AVATAR_SOURCES = (
            (AVATAR_FROM_GRAVATAR, 'Hosted by Gravatar'),
            (AVATAR_FROM_USER, 'Uploaded by user'),
            (AVATAR_FROM_SYSTEM, 'System generated'),
    )
    avatar_source = models.CharField(default=AVATAR_FROM_GRAVATAR, choices=AVATAR_SOURCES, max_length=1)

    TUTORIAL_WAITING  = 'W'
    TUTORIAL_STARTED  = 'S'
    TUTORIAL_FINISHED = 'F'
    TUTORIAL_STATES   = ((TUTORIAL_WAITING,  "Waiting"),
                         (TUTORIAL_STARTED,  "Started"),
                         (TUTORIAL_FINISHED, "Finished"))

    tutorial_status = models.CharField(default=TUTORIAL_WAITING, choices=TUTORIAL_STATES, max_length=1)
    # Contains serialized JSON of the form:
    #    [("step 1", true), ("step 2", false)]
    # where the second element of each tuple is if the step has been
    # completed.
    onboarding_steps = models.TextField(default=ujson.dumps([]))

    def tutorial_stream_name(self):
        # If you change this, you need to change the corresponding
        # client-computed version of it in tutorial.js
        long_name = "tutorial-%s" % (self.email.split('@')[0],)
        short_name = long_name[:Stream.MAX_NAME_LENGTH]
        return short_name

    objects = UserManager()

    def __repr__(self):
        return (u"<UserProfile: %s %s>" % (self.email, self.realm)).encode("utf-8")
    def __str__(self):
        return self.__repr__()

# Make sure we flush the UserProfile object from our memcached
# whenever we save it.
post_save.connect(update_user_profile_cache, sender=UserProfile)

class PreregistrationUser(models.Model):
    email = models.EmailField()
    referred_by = models.ForeignKey(UserProfile, null=True)
    streams = models.ManyToManyField('Stream', null=True)
    invited_at = models.DateTimeField(auto_now=True)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0)

class MitUser(models.Model):
    email = models.EmailField(unique=True)
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_ACTIVE
    status = models.IntegerField(default=0)

class Stream(models.Model):
    # If you change this, you also need to change the
    # corresponding value in tutorial.js
    MAX_NAME_LENGTH = 30
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True)
    realm = models.ForeignKey(Realm, db_index=True)
    invite_only = models.NullBooleanField(default=False)

    def __repr__(self):
        return (u"<Stream: %s>" % (self.name,)).encode("utf-8")
    def __str__(self):
        return self.__repr__()

    def is_public(self):
        # For every realm except for legacy realms on prod (aka those
        # older than realm id 68 with some exceptions), we enable
        # historical messages for all streams that are not invite-only.
        return ((not settings.DEPLOYED or self.realm.domain in
                 ["humbughq.com"] or self.realm.id > 68)
                and not self.invite_only)

    class Meta:
        unique_together = ("name", "realm")

    @classmethod
    def create(cls, name, realm):
        stream = cls(name=name, realm=realm)
        stream.save()

        recipient = Recipient.objects.create(type_id=stream.id,
                                             type=Recipient.STREAM)
        return (stream, recipient)

def valid_stream_name(name):
    return name != ""

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
        return (u"<Recipient: %s (%d, %s)>" % (display_recipient, self.type_id, self.type)).encode("utf-8")

class Client(models.Model):
    name = models.CharField(max_length=30, db_index=True, unique=True)

def get_client_cache_key(name):
    return 'get_client:%s' % (make_safe_digest(name),)

@cache_with_key(get_client_cache_key, timeout=3600*24*7)
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

def get_stream_cache_key(stream_name, realm):
    if isinstance(realm, Realm):
        realm_id = realm.id
    else:
        realm_id = realm
    return "stream_by_realm_and_name:%s:%s" % (
        realm_id, make_safe_digest(stream_name.strip().lower()))

# get_stream_backend takes either a realm id or a realm
@cache_with_key(get_stream_cache_key, timeout=3600*24*7)
def get_stream_backend(stream_name, realm):
    if isinstance(realm, Realm):
        realm_id = realm.id
    else:
        realm_id = realm
    return Stream.objects.select_related("realm").get(
        name__iexact=stream_name.strip(), realm_id=realm_id)

# get_stream takes either a realm id or a realm
def get_stream(stream_name, realm):
    try:
        return get_stream_backend(stream_name, realm)
    except Stream.DoesNotExist:
        return None

def bulk_get_streams(realm, stream_names):
    if isinstance(realm, Realm):
        realm_id = realm.id
    else:
        realm_id = realm

    def fetch_streams_by_name(stream_names):
        # This should be just
        #
        # Stream.objects.select_related("realm").filter(name__iexact__in=stream_names,
        #                                               realm_id=realm_id)
        #
        # But chaining __in and __iexact doesn't work with Django's
        # ORM, so we have the following hack to construct the relevant where clause
        if len(stream_names) == 0:
            return []
        upper_list = ", ".join(["UPPER(%s)"] * len(stream_names))
        where_clause = "UPPER(zephyr_stream.name::text) IN (%s)" % (upper_list,)
        return Stream.objects.select_related("realm").filter(realm_id=realm_id).extra(
            where=[where_clause],
            params=stream_names)

    return generic_bulk_cached_fetch(lambda stream_name: get_stream_cache_key(stream_name, realm),
                                     fetch_streams_by_name,
                                     [stream_name.lower() for stream_name in stream_names],
                                     id_fetcher=lambda stream: stream.name.lower())

def get_recipient_cache_key(type, type_id):
    return "get_recipient:%s:%s" % (type, type_id,)

@cache_with_key(get_recipient_cache_key, timeout=3600*24*7)
def get_recipient(type, type_id):
    return Recipient.objects.get(type_id=type_id, type=type)

def bulk_get_recipients(type, type_ids):
    def cache_key_function(type_id):
        return get_recipient_cache_key(type, type_id)
    def query_function(type_ids):
        return Recipient.objects.filter(type=type, type_id__in=type_ids)

    return generic_bulk_cached_fetch(cache_key_function, query_function, type_ids,
                                     id_fetcher=lambda recipient: recipient.type_id)

# NB: This function is currently unused, but may come in handy.
def linebreak(string):
    return string.replace('\n\n', '<p/>').replace('\n', '<br/>')

def extract_message_dict(message_str):
    return ujson.loads(zlib.decompress(message_str))

def stringify_message_dict(message_dict):
    return zlib.compress(ujson.dumps(message_dict))

def to_dict_cache_key_id(message_id, apply_markdown, rendered_content=None):
    return 'message_dict:%d:%d' % (message_id, apply_markdown)

def to_dict_cache_key(message, apply_markdown, rendered_content=None):
    return to_dict_cache_key_id(message.id, apply_markdown, rendered_content=None)

class Message(models.Model):
    sender = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    subject = models.CharField(max_length=MAX_SUBJECT_LENGTH, db_index=True)
    content = models.TextField()
    rendered_content = models.TextField(null=True)
    rendered_content_version = models.IntegerField(null=True)
    pub_date = models.DateTimeField('date published', db_index=True)
    sending_client = models.ForeignKey(Client)
    last_edit_time = models.DateTimeField(null=True)
    edit_history = models.TextField(null=True)

    def __repr__(self):
        display_recipient = get_display_recipient(self.recipient)
        return (u"<Message: %s / %s / %r>" % (display_recipient, self.subject, self.sender)).encode("utf-8")
    def __str__(self):
        return self.__repr__()

    def to_dict(self, apply_markdown, rendered_content=None):
        return extract_message_dict(self.to_dict_json(apply_markdown, rendered_content))

    @cache_with_key(to_dict_cache_key, timeout=3600*24)
    def to_dict_json(self, apply_markdown, rendered_content=None):
        return stringify_message_dict(self.to_dict_uncached(apply_markdown, rendered_content))

    def to_dict_uncached(self, apply_markdown, rendered_content=None):
        display_recipient = get_display_recipient(self.recipient)
        if self.recipient.type == Recipient.STREAM:
            display_type = "stream"
        elif self.recipient.type in (Recipient.HUDDLE, Recipient.PERSONAL):
            display_type = "private"
            if len(display_recipient) == 1:
                # add the sender in if this isn't a message between
                # someone and his self, preserving ordering
                recip = {'email': self.sender.email,
                         'domain': self.sender.realm.domain,
                         'full_name': self.sender.full_name,
                         'short_name': self.sender.short_name};
                if recip['email'] < display_recipient[0]['email']:
                    display_recipient = [recip, display_recipient[0]]
                elif recip['email'] > display_recipient[0]['email']:
                    display_recipient = [display_recipient[0], recip]
        else:
            display_type = self.recipient.type_name()

        obj = dict(
            id                = self.id,
            sender_email      = self.sender.email,
            sender_full_name  = self.sender.full_name,
            sender_short_name = self.sender.short_name,
            sender_domain     = self.sender.realm.domain,
            type              = display_type,
            display_recipient = display_recipient,
            recipient_id      = self.recipient.id,
            subject           = self.subject,
            timestamp         = datetime_to_timestamp(self.pub_date),
            gravatar_hash     = gravatar_hash(self.sender.email), # Deprecated June 2013
            avatar_url        = avatar_url(self.sender),
            client            = self.sending_client.name)

        if self.last_edit_time != None:
            obj['last_edit_timestamp'] = datetime_to_timestamp(self.last_edit_time)
            obj['edit_history'] = ujson.loads(self.edit_history)
        if apply_markdown and self.rendered_content_version is not None:
            obj['content'] = self.rendered_content
            obj['content_type'] = 'text/html'
        elif apply_markdown:
            if rendered_content is None:
                rendered_content = bugdown.convert(self.content, self.sender.realm.domain)
                if rendered_content is None:
                    rendered_content = '<p>[Humbug note: Sorry, we could not understand the formatting of your message]</p>'

                # Update the database cache of the rendered content
                self.rendered_content = rendered_content
                self.rendered_content_version = bugdown.version
                self.save(update_fields=["rendered_content", "rendered_content_version"])
            obj['content'] = rendered_content
            obj['content_type'] = 'text/html'
        else:
            obj['content'] = self.content
            obj['content_type'] = 'text/x-markdown'

        return obj

    def to_log_dict(self):
        return dict(
            id                = self.id,
            sender_email      = self.sender.email,
            sender_domain     = self.sender.realm.domain,
            sender_full_name  = self.sender.full_name,
            sender_short_name = self.sender.short_name,
            sending_client    = self.sending_client.name,
            type              = self.recipient.type_name(),
            recipient         = get_display_recipient(self.recipient),
            subject           = self.subject,
            content           = self.content,
            timestamp         = datetime_to_timestamp(self.pub_date))

    @classmethod
    def remove_unreachable(cls):
        """Remove all Messages that are not referred to by any UserMessage."""
        cls.objects.exclude(id__in = UserMessage.objects.values('message_id')).delete()

class UserMessage(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    message = models.ForeignKey(Message)
    # We're not using the archived field for now, but create it anyway
    # since this table will be an unpleasant one to do schema changes
    # on later
    archived = models.BooleanField()
    ALL_FLAGS = ['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned']
    flags = BitField(flags=ALL_FLAGS, default=0)

    class Meta:
        unique_together = ("user_profile", "message")

    def __repr__(self):
        display_recipient = get_display_recipient(self.message.recipient)
        return (u"<UserMessage: %s / %s (%s)>" % (display_recipient, self.user_profile.email, self.flags_list())).encode("utf-8")

    def flags_list(self):
        return [flag for flag in self.flags.keys() if getattr(self.flags, flag).is_set]

def parse_usermessage_flags(val):
    flags = []
    mask = 1
    for flag in UserMessage.ALL_FLAGS:
        if val & mask:
            flags.append(flag)
        mask <<= 1
    return flags

class Subscription(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    active = models.BooleanField(default=True)
    in_home_view = models.NullBooleanField(default=True)

    DEFAULT_STREAM_COLOR = "#c2c2c2"
    color = models.CharField(max_length=10, default=DEFAULT_STREAM_COLOR)
    notifications = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user_profile", "recipient")

    def __repr__(self):
        return (u"<Subscription: %r -> %s>" % (self.user_profile, self.recipient)).encode("utf-8")
    def __str__(self):
        return self.__repr__()

@cache_with_key(user_profile_by_id_cache_key, timeout=3600*24*7)
def get_user_profile_by_id(uid):
    return UserProfile.objects.select_related().get(id=uid)

@cache_with_key(user_profile_by_email_cache_key, timeout=3600*24*7)
def get_user_profile_by_email(email):
    return UserProfile.objects.select_related().get(email__iexact=email)

def get_prereg_user_by_email(email):
    # A user can be invited many times, so only return the result of the latest
    # invite.
    return PreregistrationUser.objects.filter(email__iexact=email).latest("invited_at")

class Huddle(models.Model):
    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True, unique=True)

def get_huddle_hash(id_list):
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    return make_safe_digest(hash_key)

def huddle_hash_cache_key(huddle_hash):
    return "huddle_by_hash:%s" % (huddle_hash,)

def get_huddle(id_list):
    huddle_hash = get_huddle_hash(id_list)
    return get_huddle_backend(huddle_hash, id_list)

@cache_with_key(lambda huddle_hash, id_list: huddle_hash_cache_key(huddle_hash), timeout=3600*24*7)
def get_huddle_backend(huddle_hash, id_list):
    (huddle, created) = Huddle.objects.get_or_create(huddle_hash=huddle_hash)
    if created:
        with transaction.commit_on_success():
            recipient = Recipient.objects.create(type_id=huddle.id,
                                                 type=Recipient.HUDDLE)
            subs_to_create = [Subscription(recipient=recipient,
                                           user_profile=get_user_profile_by_id(user_profile_id))
                              for user_profile_id in id_list]
            Subscription.objects.bulk_create(subs_to_create)
    return huddle

def get_realm(domain):
    try:
        return Realm.objects.get(domain__iexact=domain.strip())
    except Realm.DoesNotExist:
        return None

def clear_database():
    for model in [Message, Stream, UserProfile, Recipient,
                  Realm, Subscription, Huddle, UserMessage, Client,
                  DefaultStream]:
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

class UserPresence(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    client = models.ForeignKey(Client)

    # Valid statuses
    ACTIVE = 1
    IDLE = 2

    timestamp = models.DateTimeField('presence changed')
    status = models.PositiveSmallIntegerField(default=ACTIVE)

    def to_dict(self):
        if self.status == UserPresence.ACTIVE:
            presence_val = 'active'
        elif self.status == UserPresence.IDLE:
            presence_val = 'idle'

        return {'client'   : self.client.name,
                'status'   : presence_val,
                'timestamp': datetime_to_timestamp(self.timestamp)}

    @staticmethod
    def status_from_string(status):
        if status == 'active':
            status_val = UserPresence.ACTIVE
        elif status == 'idle':
            status_val = UserPresence.IDLE
        else:
            status_val = None

        return status_val

    class Meta:
        unique_together = ("user_profile", "client")

# Flush the cached user status_dict whenever a user's presence
# changes
post_save.connect(update_user_presence_cache, sender=UserPresence)

class DefaultStream(models.Model):
    realm = models.ForeignKey(Realm)
    stream = models.ForeignKey(Stream)

    class Meta:
        unique_together = ("realm", "stream")

# FIXME: The foreign key relationship here is backwards.
#
# We can't easily get a list of streams and their associated colors (if any) in
# a single query.  See zephyr.views.gather_subscriptions for an example.
#
# We should change things around so that is possible.  Probably this should
# just be a column on Subscription.
class StreamColor(models.Model):
    DEFAULT_STREAM_COLOR = "#c2c2c2"

    subscription = models.ForeignKey(Subscription)
    color = models.CharField(max_length=10)
