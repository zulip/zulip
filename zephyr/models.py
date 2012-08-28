from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    pointer = models.IntegerField()

class ZephyrClass(models.Model):
    name = models.CharField(max_length=30)

class Recipient(models.Model):
    user_or_class = models.IntegerField()
    type = models.CharField(max_length=30)

class Zephyr(models.Model):
    sender = models.ForeignKey(UserProfile)
    recipient = models.ForeignKey(Recipient) # personal or class
    instance = models.CharField(max_length=30)
    content = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

def create_user_profile(**kwargs):
    """When creating a new user, make a profile for him or her."""
    u = kwargs["instance"]
    if not UserProfile.objects.filter(user=u):
        UserProfile(user=u, pointer=-1).save()
post_save.connect(create_user_profile, sender=User)
