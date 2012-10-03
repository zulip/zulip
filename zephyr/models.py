from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
import hashlib
import base64
import calendar
from zephyr.lib.cache import cache_with_key
import fcntl
import os
import simplejson

import markdown
md_engine = markdown.Markdown(
    extensions    = ['fenced_code', 'codehilite', 'nl2br'],
    output_format = 'xhtml' )

def get_display_recipient(recipient):
    """
    recipient: an instance of Recipient.

    returns: an appropriate string describing the recipient (the class
    name, for a class, or the email, for a user).
    """
    if recipient.type == Recipient.CLASS:
        zephyr_class = ZephyrClass.objects.get(id=recipient.type_id)
        return zephyr_class.name
    elif recipient.type == Recipient.HUDDLE:
        user_profile_list = [UserProfile.objects.get(user=s.userprofile) for s in
                             Subscription.objects.filter(recipient=recipient)]
        return [{'email': user_profile.user.email,
                 'name': user_profile.short_name} for user_profile in user_profile_list]
    else:
        user = User.objects.get(id=recipient.type_id)
        return user.email

def get_log_recipient(recipient):
    """
    recipient: an instance of Recipient.

    returns: an appropriate string describing the recipient (the class
    name, for a class, or the email, for a user).
    """
    if recipient.type == Recipient.CLASS:
        zephyr_class = ZephyrClass.objects.get(id=recipient.type_id)
        return zephyr_class.name

    user_profile_list = [UserProfile.objects.get(user=s.userprofile) for s in
                         Subscription.objects.filter(recipient=recipient)]
    return [{'email': user_profile.user.email,
             'full_name': user_profile.full_name,
             'short_name': user_profile.short_name} for user_profile in user_profile_list]

callback_table = {}
mit_sync_table = {}

class Realm(models.Model):
    domain = models.CharField(max_length=40, db_index=True)

    def __repr__(self):
        return "<Realm: %s %s>" % (self.domain, self.id)
    def __str__(self):
        return self.__repr__()

def gen_api_key():
    return 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
### TODO: For now, everyone has the same (fixed) API key to make
### testing easier.  Uncomment the following to generate them randomly
### in a reasonable way.  Long-term, we should use a real
### cryptographic random number generator.

#    return hex(random.getrandbits(4*32))[2:34]

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    full_name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=100)
    pointer = models.IntegerField()
    realm = models.ForeignKey(Realm)
    api_key = models.CharField(max_length=32)

    # The user receives this message
    def receive(self, message):
        global callback_table

        # Should also store in permanent database the receipt
        um = UserMessage(user_profile=self, message=message)
        um.save()

        for cb in callback_table.get(self.user.id, []):
            cb([message])

        callback_table[self.user.id] = []

    def add_callback(self, cb):
        global callback_table
        callback_table.setdefault(self.user.id, []).append(cb)

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
            profile.api_key = gen_api_key()
            profile.save()
            # Auto-sub to the ability to receive personals.
            recipient = Recipient(type_id=profile.id, type=Recipient.PERSONAL)
            recipient.save()
            Subscription(userprofile=profile, recipient=recipient).save()

class PreregistrationUser(models.Model):
    email = models.EmailField(unique=True)
    # 0 is inactive, 1 is active
    status = models.IntegerField(default=0)

def create_user(email, password, realm, full_name, short_name):
    # NB: the result of Base32 + truncation is not a valid Base32 encoding.
    # It's just a unique alphanumeric string.
    # Use base32 instead of base64 so we don't have to worry about mixed case.
    # Django imposes a limit of 30 characters on usernames.
    email_hash = hashlib.sha256(settings.HASH_SALT + email).digest()
    username = base64.b32encode(email_hash)[:30]
    user = User.objects.create_user(username=username, password=password,
                                    email=email)
    user.save()
    UserProfile.create(user, realm, full_name, short_name)

def create_user_if_needed(realm, email, password, full_name, short_name):
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        # forge a user for this person
        create_user(email, password, realm,
                    full_name, short_name)
        user = User.objects.get(email=email)
        return user

def create_class_if_needed(realm, class_name):
    try:
        return ZephyrClass.objects.get(name__iexact=class_name, realm=realm)
    except ZephyrClass.DoesNotExist:
        new_class = ZephyrClass()
        new_class.name = class_name
        new_class.realm = realm
        new_class.save()
        recipient = Recipient(type_id=new_class.id, type=Recipient.CLASS)
        recipient.save()
        return new_class


class ZephyrClass(models.Model):
    name = models.CharField(max_length=30, db_index=True)
    realm = models.ForeignKey(Realm, db_index=True)

    def __repr__(self):
        return "<ZephyrClass: %s>" % (self.name,)
    def __str__(self):
        return self.__repr__()

    @classmethod
    def create(cls, name, realm):
        zephyr_class = cls(name=name, realm=realm)
        zephyr_class.save()

        recipient = Recipient(type_id=zephyr_class.id, type=Recipient.CLASS)
        recipient.save()
        return (zephyr_class, recipient)

class Recipient(models.Model):
    type_id = models.IntegerField(db_index=True)
    type = models.PositiveSmallIntegerField(db_index=True)
    # Valid types are {personal, class, huddle}
    PERSONAL = 1
    CLASS = 2
    HUDDLE = 3

    def type_name(self):
        if self.type == self.PERSONAL:
            return "personal"
        elif self.type == self.CLASS:
            return "class"
        elif self.type == self.HUDDLE:
            return "huddle"
        else:
            raise

    def __repr__(self):
        display_recipient = get_display_recipient(self)
        return "<Recipient: %s (%d, %s)>" % (display_recipient, self.type_id, self.type)

class Message(models.Model):
    sender = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    instance = models.CharField(max_length=30)
    content = models.TextField()
    pub_date = models.DateTimeField('date published')

    def __repr__(self):
        display_recipient = get_display_recipient(self.recipient)
        return "<Message: %s / %s / %r>" % (display_recipient, self.instance, self.sender)
    def __str__(self):
        return self.__repr__()

    @cache_with_key(lambda self, apply_markdown: 'message_dict:%d:%d' % (self.id, apply_markdown))
    def to_dict(self, apply_markdown):
        if apply_markdown:
            content = md_engine.convert(self.content)
        else:
            content = self.content
        return {'id'               : self.id,
                'sender_email'     : self.sender.user.email,
                'sender_name'      : self.sender.full_name,
                'type'             : self.recipient.type_name(),
                'display_recipient': get_display_recipient(self.recipient),
                'recipient_id'     : self.recipient.id,
                'instance'         : self.instance,
                'content'          : content,
                'timestamp'        : calendar.timegm(self.pub_date.timetuple()),
                'gravatar_hash'    : hashlib.md5(self.sender.user.email.lower()).hexdigest(),
                }

    def to_log_dict(self):
        return {'id'               : self.id,
                'sender_email'     : self.sender.user.email,
                'sender_full_name' : self.sender.full_name,
                'sender_short_name': self.sender.full_name,
                'type'             : self.recipient.type_name(),
                'recipient'        : get_log_recipient(self.recipient),
                'instance'         : self.instance,
                'content'          : self.content,
                'timestamp'        : self.pub_date.strftime("%s"),
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
    return UserProfile.objects.get(id=uid)

def log_message(message):
    if not os.path.exists(settings.MESSAGE_LOG + '.lock'):
        file(settings.MESSAGE_LOG + '.lock', "w").write("0")
    lock = open(settings.MESSAGE_LOG + '.lock', 'r')
    fcntl.flock(lock, fcntl.LOCK_EX)
    f = open(settings.MESSAGE_LOG, "a")
    f.write(simplejson.dumps(message.to_log_dict()) + "\n")
    f.flush()
    f.close()
    fcntl.flock(lock, fcntl.LOCK_UN)

def do_send_message(message, synced_from_mit=False, no_log=False):
    message.save()
    # The following mit_sync_table code must be after message.save() or
    # otherwise the id returned will be None (not having been assigned
    # by the database yet)
    mit_sync_table[message.id] = synced_from_mit
    # Log the message to our message log for populate_db to refill
    if not no_log:
        log_message(message)

    if message.recipient.type == Recipient.PERSONAL:
        recipients = list(set([get_user_profile_by_id(message.recipient.type_id),
                               get_user_profile_by_id(message.sender_id)]))
        # For personals, you send out either 1 or 2 copies of the message, for
        # personals to yourself or to someone else, respectively.
        assert((len(recipients) == 1) or (len(recipients) == 2))
    elif (message.recipient.type == Recipient.CLASS or
          message.recipient.type == Recipient.HUDDLE):
        recipients = [get_user_profile_by_id(s.userprofile_id) for
                      s in Subscription.objects.filter(recipient=message.recipient, active=True)]
    else:
        raise
    for recipient in recipients:
        recipient.receive(message)

class Subscription(models.Model):
    userprofile = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    active = models.BooleanField(default=True)

    def __repr__(self):
        return "<Subscription: %r -> %r>" % (self.userprofile, self.recipient)
    def __str__(self):
        return self.__repr__()

class Huddle(models.Model):
    # TODO: We should consider whether using
    # CommaSeparatedIntegerField would be better.
    huddle_hash = models.CharField(max_length=40, db_index=True)

def get_huddle(id_list):
    id_list = sorted(set(id_list))
    hash_key = ",".join(str(x) for x in id_list)
    huddle_hash = hashlib.sha1(hash_key).hexdigest()
    if Huddle.objects.filter(huddle_hash=huddle_hash):
        return Huddle.objects.get(huddle_hash=huddle_hash)
    else:
        # since we don't have one, make a new huddle
        huddle = Huddle(huddle_hash = huddle_hash)
        huddle.save()
        recipient = Recipient(type_id=huddle.id, type=Recipient.HUDDLE)
        recipient.save()

        # Add subscriptions
        for uid in id_list:
            s = Subscription(recipient = recipient,
                             userprofile = UserProfile.objects.get(id=uid))
            s.save()
        return huddle

# This is currently dead code since all the places where we used to
# use it now have faster implementations, but I expect this to be
# potentially useful for code in the future, so not deleting it yet.
def filter_by_subscriptions(messages, user):
    userprofile = UserProfile.objects.get(user=user)
    user_messages = []
    subscriptions = [sub.recipient for sub in
                     Subscription.objects.filter(userprofile=userprofile, active=True)]
    for message in messages:
        # If you are subscribed to the personal or class, or if you
        # sent the personal, you can see the message.
        if (message.recipient in subscriptions) or \
                (message.recipient.type == Recipient.PERSONAL and
                 message.sender == userprofile):
            user_messages.append(message)

    return user_messages
