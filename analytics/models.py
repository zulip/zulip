import datetime
from typing import Optional

from django.db import models
from django.db.models import Q, UniqueConstraint

from zerver.lib.timestamp import floor_to_day
from zerver.models import Realm, Stream, UserProfile

class FillState(models.Model):
    property = models.CharField(max_length=40, unique=True)  # type: str
    end_time = models.DateTimeField()  # type: datetime.datetime

    # Valid states are {DONE, STARTED}
    DONE = 1
    STARTED = 2
    state = models.PositiveSmallIntegerField()  # type: int

    def __str__(self) -> str:
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

class BaseCount(models.Model):
    # Note: When inheriting from BaseCount, you may want to rearrange
    # the order of the columns in the migration to make sure they
    # match how you'd like the table to be arranged.
    property = models.CharField(max_length=32)  # type: str
    subgroup = models.CharField(max_length=16, null=True)  # type: Optional[str]
    end_time = models.DateTimeField()  # type: datetime.datetime
    value = models.BigIntegerField()  # type: int

    class Meta:
        abstract = True

class InstallationCount(BaseCount):

    class Meta:
        # Handles invalid duplicate InstallationCount data
        constraints = [
            UniqueConstraint(
                fields=["property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name='unique_installation_count'),
            UniqueConstraint(
                fields=["property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name='unique_installation_count_null_subgroup')
        ]

    def __str__(self) -> str:
        return "<InstallationCount: %s %s %s>" % (self.property, self.subgroup, self.value)

class RealmCount(BaseCount):
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        # Handles invalid duplicate RealmCount data
        constraints = [
            UniqueConstraint(
                fields=["realm", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name='unique_realm_count'),
            UniqueConstraint(
                fields=["realm", "property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name='unique_realm_count_null_subgroup')
        ]
        index_together = ["property", "end_time"]

    def __str__(self) -> str:
        return "<RealmCount: %s %s %s %s>" % (self.realm, self.property, self.subgroup, self.value)

class UserCount(BaseCount):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        # Handles invalid duplicate UserCount data
        constraints = [
            UniqueConstraint(
                fields=["user", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name='unique_user_count'),
            UniqueConstraint(
                fields=["user", "property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name='unique_user_count_null_subgroup')
        ]
        # This index dramatically improves the performance of
        # aggregating from users to realms
        index_together = ["property", "realm", "end_time"]

    def __str__(self) -> str:
        return "<UserCount: %s %s %s %s>" % (self.user, self.property, self.subgroup, self.value)

class StreamCount(BaseCount):
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE)
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        # Handles invalid duplicate StreamCount data
        constraints = [
            UniqueConstraint(
                fields=["stream", "property", "subgroup", "end_time"],
                condition=Q(subgroup__isnull=False),
                name='unique_stream_count'),
            UniqueConstraint(
                fields=["stream", "property", "end_time"],
                condition=Q(subgroup__isnull=True),
                name='unique_stream_count_null_subgroup')
        ]
        # This index dramatically improves the performance of
        # aggregating from streams to realms
        index_together = ["property", "realm", "end_time"]

    def __str__(self) -> str:
        return "<StreamCount: %s %s %s %s %s>" % (
            self.stream, self.property, self.subgroup, self.value, self.id)
