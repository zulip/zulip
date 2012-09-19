from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.signals import post_save
import hashlib
import calendar
import datetime
from zephyr.lib.cache import cache_with_key

def get_display_recipient(recipient):
    """
    recipient: an instance of Recipient.

    returns: an appropriate string describing the recipient (the class
    name, for a class, or the username, for a user).
    """
    if recipient.type == Recipient.CLASS:
        zephyr_class = ZephyrClass.objects.get(id=recipient.type_id)
        return zephyr_class.name
    elif recipient.type == Recipient.HUDDLE:
        user_list = [UserProfile.objects.get(user=s.userprofile) for s in
                     Subscription.objects.filter(recipient=recipient)]
        return [{'name': user.short_name} for user in user_list]
    else:
        user = User.objects.get(id=recipient.type_id)
        return user.username

callback_table = {}

class Realm(models.Model):
    domain = models.CharField(max_length=40, db_index=True)

    def __repr__(self):
        return "<Realm: %s %s>" % (self.domain, self.id)
    def __str__(self):
        return self.__repr__()

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    full_name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=100)
    pointer = models.IntegerField()
    realm = models.ForeignKey(Realm)

    # The user receives this message
    def receive(self, message):
        global callback_table

        # Should also store in permanent database the receipt
        um = UserMessage(user_profile=self, message=message)
        um.save()

        for cb in callback_table.get(self.user.id, []):
            cb([message])

        callback_table[self.user.id] = []

    def add_callback(self, cb, last_received):
        global callback_table

        new_zephyrs = [um.message for um in
                       UserMessage.objects.filter(user_profile=self,
                                                  message__id__gt=last_received)]

        if new_zephyrs:
            return cb(new_zephyrs)
        callback_table.setdefault(self.user.id, []).append(cb)

    def __repr__(self):
        return "<UserProfile: %s %s>" % (self.user.username, self.realm)
    def __str__(self):
        return self.__repr__()

    @classmethod
    def create(cls, user, realm, full_name, short_name):
        """When creating a new user, make a profile for him or her."""
        if not cls.objects.filter(user=user):
            profile = cls(user=user, pointer=-1, realm_id=realm.id,
                          full_name=full_name, short_name=short_name)
            profile.save()
            # Auto-sub to the ability to receive personals.
            recipient = Recipient(type_id=profile.id, type=Recipient.PERSONAL)
            recipient.save()
            Subscription(userprofile=profile, recipient=recipient).save()

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

class Zephyr(models.Model):
    sender = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient)
    instance = models.CharField(max_length=30)
    content = models.TextField()
    pub_date = models.DateTimeField('date published')

    def __repr__(self):
        display_recipient = get_display_recipient(self.recipient)
        return "<Zephyr: %s / %s / %r>" % (display_recipient, self.instance, self.sender)
    def __str__(self):
        return self.__repr__()

    @cache_with_key(lambda self: 'zephyr_dict:%d' % (self.id,))
    def to_dict(self):
        return {'id'               : self.id,
                'sender'           : self.sender.user.username,
                'sender_email'     : self.sender.user.email,
                'sender_name'      : self.sender.full_name,
                'type'             : self.recipient.type_name(),
                'display_recipient': get_display_recipient(self.recipient),
                'instance'         : self.instance,
                'content'          : self.content,
                'timestamp'        : calendar.timegm(self.pub_date.timetuple()),
                'gravatar_hash'    : hashlib.md5(settings.MD5_SALT + self.sender.user.email).hexdigest(),
                }

class UserMessage(models.Model):
    user_profile = models.ForeignKey(UserProfile)
    message = models.ForeignKey(Zephyr)
    # We're not using the archived field for now, but create it anyway
    # since this table will be an unpleasant one to do schema changes
    # on later
    archived = models.BooleanField()

    def __repr__(self):
        display_recipient = get_display_recipient(self.message.recipient)
        return "<UserMessage: %s / %s>" % (display_recipient, self.user_profile.user.username)

user_hash = {}
def get_user_profile_by_id(uid):
    if uid in user_hash:
        return user_hash[uid]
    return UserProfile.objects.get(id=uid)

def send_zephyr(**kwargs):
    zephyr = kwargs["instance"]
    if zephyr.recipient.type == Recipient.PERSONAL:
        recipients = list(set([get_user_profile_by_id(zephyr.recipient.type_id),
                               get_user_profile_by_id(zephyr.sender_id)]))
        # For personals, you send out either 1 or 2 copies of the zephyr, for
        # personals to yourself or to someone else, respectively.
        assert((len(recipients) == 1) or (len(recipients) == 2))
    elif (zephyr.recipient.type == Recipient.CLASS or
          zephyr.recipient.type == Recipient.HUDDLE):
        recipients = [get_user_profile_by_id(s.userprofile_id) for
                      s in Subscription.objects.filter(recipient=zephyr.recipient, active=True)]
    else:
        raise
    for recipient in recipients:
        recipient.receive(zephyr)

post_save.connect(send_zephyr, sender=Zephyr)

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
def filter_by_subscriptions(zephyrs, user):
    userprofile = UserProfile.objects.get(user=user)
    subscribed_zephyrs = []
    subscriptions = [sub.recipient for sub in
                     Subscription.objects.filter(userprofile=userprofile, active=True)]
    for zephyr in zephyrs:
        # If you are subscribed to the personal or class, or if you
        # sent the personal, you can see the zephyr.
        if (zephyr.recipient in subscriptions) or \
                (zephyr.recipient.type == Recipient.PERSONAL and
                 zephyr.sender == userprofile):
            subscribed_zephyrs.append(zephyr)

    return subscribed_zephyrs
