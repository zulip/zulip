import datetime
from typing import Any, Dict, Optional, Text, Tuple, Union

from django.db import models

from zerver.lib.timestamp import floor_to_day
from zerver.models import Realm, Recipient, Stream, UserProfile

class FillState(models.Model):
    property = models.CharField(max_length=40, unique=True)  # type: Text
    end_time = models.DateTimeField()  # type: datetime.datetime

    # Valid states are {DONE, STARTED}
    DONE = 1
    STARTED = 2
    state = models.PositiveSmallIntegerField()  # type: int

    last_modified = models.DateTimeField(auto_now=True)  # type: datetime.datetime

    def __str__(self) -> Text:
        return "<FillState: %s %s %s>" % (self.property, self.end_time, self.state)

# The earliest/starting end_time in FillState
# We assume there is at least one realm
def installation_epoch() -> datetime.datetime:
    earliest_realm_creation = Realm.objects.aggregate(models.Min('date_created'))['date_created__min']
    return floor_to_day(earliest_realm_creation)

def last_successful_fill(property: str) -> Optional[datetime.datetime]:
    fillstate = FillState.objects.filter(property=property).first()
    if fillstate is None:
        return None
    if fillstate.state == FillState.DONE:
        return fillstate.end_time
    return fillstate.end_time - datetime.timedelta(hours=1)

# would only ever make entries here by hand
class Anomaly(models.Model):
    info = models.CharField(max_length=1000)  # type: Text

    def __str__(self) -> Text:
        return "<Anomaly: %s... %s>" % (self.info, self.id)

class BaseCount(models.Model):
    # Note: When inheriting from BaseCount, you may want to rearrange
    # the order of the columns in the migration to make sure they
    # match how you'd like the table to be arranged.
    property = models.CharField(max_length=32)  # type: Text
    subgroup = models.CharField(max_length=16, null=True)  # type: Optional[Text]
    end_time = models.DateTimeField()  # type: datetime.datetime
    value = models.BigIntegerField()  # type: int
    anomaly = models.ForeignKey(Anomaly, on_delete=models.SET_NULL, null=True)  # type: Optional[Anomaly]

    class Meta:
        abstract = True

class InstallationCount(BaseCount):

    class Meta:
        unique_together = ("property", "subgroup", "end_time")

    def __str__(self) -> Text:
        return "<InstallationCount: %s %s %s>" % (self.property, self.subgroup, self.value)

class RealmCount(BaseCount):
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("realm", "property", "subgroup", "end_time")
        index_together = ["property", "end_time"]

    def __str__(self) -> Text:
        return "<RealmCount: %s %s %s %s>" % (self.realm, self.property, self.subgroup, self.value)

class UserCount(BaseCount):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "property", "subgroup", "end_time")
        # This index dramatically improves the performance of
        # aggregating from users to realms
        index_together = ["property", "realm", "end_time"]

    def __str__(self) -> Text:
        return "<UserCount: %s %s %s %s>" % (self.user, self.property, self.subgroup, self.value)

class StreamCount(BaseCount):
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE)
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("stream", "property", "subgroup", "end_time")
        # This index dramatically improves the performance of
        # aggregating from streams to realms
        index_together = ["property", "realm", "end_time"]

    def __str__(self) -> Text:
        return "<StreamCount: %s %s %s %s %s>" % (
            self.stream, self.property, self.subgroup, self.value, self.id)
