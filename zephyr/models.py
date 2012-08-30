from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save

def get_display_recipient(recipient):
    """
    recipient: an instance of Recipient.

    returns: an appropriate string describing the recipient (the class
    name, for a class, or the username, for a user).
    """
    if recipient.type == "class":
        zephyr_class = ZephyrClass.objects.get(pk=recipient.user_or_class)
        return zephyr_class.name
    else:
        user = User.objects.get(pk=recipient.user_or_class)
        return user.username

callback_table = {}

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    pointer = models.IntegerField()

    # The user receives this message
    def receive(self, message):
        global callback_table

        # Should also store in permanent database the receipt
        for cb in callback_table.get(self.user.id, []):
            cb([message])

        callback_table[self.user.id] = []

    def add_callback(self, cb, last_received):
        global callback_table

        # This filter should also restrict to the current user's subs
        new_zephyrs = Zephyr.objects.filter(id__gt=last_received)
        if new_zephyrs:
            return cb(new_zephyrs)
        callback_table.setdefault(self.user.id, []).append(cb)

    def __repr__(self):
        return "<UserProfile: %s>" % (self.user.username,)

def create_user_profile(**kwargs):
    """When creating a new user, make a profile for him or her."""
    u = kwargs["instance"]
    if not UserProfile.objects.filter(user=u):
        UserProfile(user=u, pointer=-1).save()
post_save.connect(create_user_profile, sender=User)

class ZephyrClass(models.Model):
    name = models.CharField(max_length=30)

    def __repr__(self):
        return "<ZephyrClass: %s>" % (self.name,)

class Recipient(models.Model):
    user_or_class = models.IntegerField()
    type = models.CharField(max_length=30)

    def __repr__(self):
        display_recipient = get_display_recipient(self)
        return "<Recipient: %s (%d, %s)>" % (display_recipient, self.user_or_class, self.type)

class Zephyr(models.Model):
    sender = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient) # personal or class
    instance = models.CharField(max_length=30)
    content = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

    def __repr__(self):
        display_recipient = get_display_recipient(self.recipient)
        return "<Zephyr: %s / %s / %r>" % (display_recipient, self.instance, self.sender)

    def to_dict(self):
        return {'id'               : self.id,
                'sender'           : self.sender.user.username,
                'type'             : self.recipient.type,
                'display_recipient': get_display_recipient(self.recipient),
                'instance'         : self.instance,
                'content'          : self.content }

def send_zephyr(**kwargs):
    zephyr = kwargs["instance"]
    if zephyr.recipient.type == "personal":
        recipients = UserProfile.objects.filter(user=zephyr.recipient.user_or_class)
        assert(len(recipients) == 1)
    elif zephyr.recipient.type == "class":
        recipients = [UserProfile.objects.get(user=s.userprofile_id) for
                      s in Subscription.objects.filter(recipient_id=zephyr.recipient)]
    else:
        raise
    for recipient in recipients:
        recipient.receive(zephyr)

post_save.connect(send_zephyr, sender=Zephyr)

class Subscription(models.Model):
    userprofile_id = models.ForeignKey(UserProfile)
    recipient_id = models.ForeignKey(Recipient)

    def __repr__(self):
        return "<Subscription: %r -> %r>" % (self.userprofile_id, self.recipient_id)

def filter_by_subscriptions(zephyrs, user):
    userprofile = UserProfile.objects.get(user=user)
    subscribed_zephyrs = []
    subscriptions = [sub.recipient_id for sub in Subscription.objects.filter(userprofile_id=userprofile)]
    for zephyr in zephyrs:
        # If you are subscribed to the personal or class, or if you sent the personal, you can see the zephyr.
        if (zephyr.recipient in subscriptions) or \
                (zephyr.recipient.type == "personal" and zephyr.sender == userprofile):
            subscribed_zephyrs.append(zephyr)

    return subscribed_zephyrs
