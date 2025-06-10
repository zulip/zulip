from django.db import models
from django.utils.timezone import now as timezone_now

from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class ChannelFolder(models.Model):
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 1024

    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, default="")
    rendered_description = models.TextField(default="")

    date_created = models.DateTimeField(default=timezone_now)
    creator = models.ForeignKey(UserProfile, null=True, on_delete=models.SET_NULL)
    is_archived = models.BooleanField(default=False)

    class Meta:
        unique_together = ("realm", "name")
