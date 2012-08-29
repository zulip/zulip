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

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    pointer = models.IntegerField()

    def __repr__(self):
        return "<UserProfile: %s>" % (self.user.username,)

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

def create_user_profile(**kwargs):
    """When creating a new user, make a profile for him or her."""
    u = kwargs["instance"]
    if not UserProfile.objects.filter(user=u):
        UserProfile(user=u, pointer=-1).save()
post_save.connect(create_user_profile, sender=User)
