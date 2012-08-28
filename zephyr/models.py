from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    pointer = models.IntegerField()

class ZephyrClass(models.Model):
    name = models.CharField(max_length=30)

class Zephyr(models.Model):
    sender = models.ForeignKey(UserProfile)
    zephyr_class = models.ForeignKey(ZephyrClass)
    instance = models.CharField(max_length=30)
    content = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

def create_user_profile(sender, **kwargs):
    """When creating a new user, make a profile for him or her."""
    u = kwargs["instance"]
    if not UserProfile.objects.filter(user=u):
        UserProfile(user=u, pointer=-1).save()
post_save.connect(create_user_profile, sender=User)
